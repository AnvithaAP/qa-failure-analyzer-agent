"""CLI and orchestrator entrypoint for QA Failure Analyzer Agent."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from collections import Counter
from pathlib import Path
from typing import Any

from classifier import Classifier, infer_rule_signal, validate_output
from llm import Analyzer, DEFAULT_PROMPT_VERSION
from memory import retrieve_similar, store_result
from utils import assess_log_quality, clean_log, detect_error_events, sanitize_input, split_ci_log_stream

logger = logging.getLogger("qa_failure_analyzer")

AGENT_VERSION = "1.0.0"
_CONFIDENCE_WARNING_THRESHOLD = 0.6
_LARGE_LOG_THRESHOLD = 8000
_SIMPLIFIED_LOG_CHARS = 1200
_CACHE: dict[str, dict[str, Any]] = {}
_COST_PER_1K_TOKENS = 0.0005


def _cache_key(log_text: str, prompt_version: str, deterministic: bool) -> str:
    payload = f"{prompt_version}:{deterministic}:{log_text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def should_retry(confidence: float) -> bool:
    return confidence < _CONFIDENCE_WARNING_THRESHOLD


def _build_simplified_log(log_text: str, max_chars: int = _SIMPLIFIED_LOG_CHARS) -> str:
    lines = [line.strip() for line in log_text.splitlines() if line.strip()]
    signal_lines = [
        line
        for line in lines
        if any(token in line.lower() for token in ("error", "exception", "failed", "timeout", "assert"))
    ]
    candidate = "\n".join(signal_lines or lines)
    return candidate[:max_chars]


def _pick_critical_error(cleaned_log: str) -> str:
    events = detect_error_events(cleaned_log)
    if not events:
        return cleaned_log
    prioritized = sorted(events, key=lambda event: (infer_rule_signal(event) or {"severity": 0})["severity"], reverse=True)
    return prioritized[0]


def _safe_default(reason: str, warning: str) -> dict[str, Any]:
    return {
        "root_cause": reason,
        "category": "Test Issue",
        "confidence": 0.3,
        "confidence_reason": warning,
        "suggestion": "Collect complete logs and rerun analysis.",
        "reasoning": warning,
    }


def _edge_case_output(cleaned_log: str, quality: dict[str, Any]) -> dict[str, Any] | None:
    if not cleaned_log.strip():
        return _safe_default("Log is empty after sanitization.", "Edge case: empty log input.")

    if len(cleaned_log) > 18000:
        return _safe_default(
            "Log is extremely large and was truncated before analysis.",
            "Edge case: very large log required aggressive truncation.",
        )

    if not quality["has_error_signal"]:
        return _safe_default(
            "No explicit error signatures were found in the log.",
            "Edge case: no clear error signal in log.",
        )

    if quality["multi_error"]:
        return {
            "root_cause": "Multiple conflicting errors detected; prioritized highest-severity error signature.",
            "category": "Environment Issue",
            "confidence": 0.55,
            "confidence_reason": "Edge case: conflicting errors reduce certainty.",
            "suggestion": "Split the log by failing test section and analyze independently.",
            "reasoning": "Detected multiple errors and selected the most severe deterministic signal.",
        }
    return None


def _step(name: str, start: float, summary: str, **extra: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "step": name,
        "summary": summary,
        "latency": round(time.perf_counter() - start, 4),
    }
    payload.update(extra)
    return payload


def _merge_usage(left: dict[str, float], right: dict[str, float]) -> dict[str, float]:
    return {
        "prompt_tokens": left.get("prompt_tokens", 0) + right.get("prompt_tokens", 0),
        "completion_tokens": left.get("completion_tokens", 0) + right.get("completion_tokens", 0),
        "total_tokens": left.get("total_tokens", 0) + right.get("total_tokens", 0),
    }


def _fallback_with_rules(log_text: str, classifier: Classifier) -> tuple[dict[str, Any], str]:
    base = _safe_default(
        "LLM analysis unavailable; rule-based fallback used.",
        "Fallback: LLM failed or confidence below threshold.",
    )
    classified, _ = classifier.classify_failure(base, log_text)
    classified["reasoning"] = (
        "Classified using deterministic rule-based classifier due to LLM failure/low confidence."
    )
    return validate_output(classified), "rule_based_classifier"


def run_analysis(
    log_text: str,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
    debug: bool = False,
    deterministic: bool = False,
) -> dict[str, Any]:
    if log_text is None:
        raise ValueError("Log text is missing. Provide --log or --file with content.")

    overall_start = time.perf_counter()
    steps: list[dict[str, Any]] = []
    usage: dict[str, float] = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    sanitize_start = time.perf_counter()
    sanitized, sanitize_meta = sanitize_input(log_text)
    cleaned_log = clean_log(sanitized)
    steps.append(
        _step(
            "cleaning",
            sanitize_start,
            "Sanitized and cleaned input log.",
            removed_injection_lines=sanitize_meta["removed_injection"],
            removed_suspicious_lines=sanitize_meta["removed_suspicious"],
            input_truncated=sanitize_meta["was_truncated"],
        )
    )

    quality = assess_log_quality(cleaned_log)
    edge_case = _edge_case_output(cleaned_log, quality)
    if edge_case and not quality["multi_error"]:
        validated = validate_output(edge_case)
        steps.append(_step("classification", time.perf_counter(), "Returned safe edge-case output.", decision=validated["category"]))
        steps.append(_step("validation", time.perf_counter(), "Output validated.", status="passed"))
        return {
            **validated,
            "steps": steps,
            "metrics": {"latency": round(time.perf_counter() - overall_start, 3), "tokens": 0, "cost_estimate": 0.0},
            "agent_version": AGENT_VERSION,
            "prompt_version": prompt_version,
            "deterministic": deterministic,
        }

    key = _cache_key(cleaned_log, prompt_version, deterministic)
    if key in _CACHE:
        cached = dict(_CACHE[key])
        cached["steps"] = steps + [{"step": "cache", "summary": "Used cached response.", "latency": 0.0}]
        return cached

    memory_hit = retrieve_similar(cleaned_log)
    if memory_hit:
        out = validate_output(memory_hit)
        out["reasoning"] = "Reused classification from highly similar prior log in memory."
        out["steps"] = steps + [
            {"step": "llm_analysis", "summary": "Skipped LLM due to memory hit.", "latency": 0.0},
            {"step": "classification", "summary": "Reused prior decision.", "decision": out["category"], "latency": 0.0},
            {"step": "validation", "summary": "Output validated.", "status": "passed", "latency": 0.0},
        ]
        out["metrics"] = {"latency": round(time.perf_counter() - overall_start, 3), "tokens": 0, "cost_estimate": 0.0}
        out["agent_version"] = AGENT_VERSION
        out["prompt_version"] = prompt_version
        out["deterministic"] = deterministic
        return out

    analyzer = Analyzer(prompt_version=prompt_version, debug=debug, deterministic=deterministic)
    classifier = Classifier(debug=debug)

    prioritized_log = _pick_critical_error(cleaned_log) if quality["multi_error"] else cleaned_log
    llm_input = prioritized_log

    if len(prioritized_log) > _LARGE_LOG_THRESHOLD:
        summary_start = time.perf_counter()
        summary, summary_usage = analyzer.summarize_log(prioritized_log)
        usage = _merge_usage(usage, summary_usage)
        llm_input = summary
        steps.append(_step("summarization", summary_start, "Used summarized log for large input."))

    llm_start = time.perf_counter()
    fallback_stage = "none"
    try:
        llm_result, _, llm_usage = analyzer.analyze_log(llm_input, retries=1)
        usage = _merge_usage(usage, llm_usage)
        steps.append(_step("llm_analysis", llm_start, "Primary LLM analysis completed."))

        classified, _ = classifier.classify_failure(llm_result, prioritized_log)
        validated = validate_output(classified)

        if should_retry(validated["confidence"]):
            retry1_start = time.perf_counter()
            retry_result, _, retry_usage = analyzer.analyze_log(llm_input, retries=1, stronger_prompt=True)
            usage = _merge_usage(usage, retry_usage)
            retry_classified = validate_output(classifier.classify_failure(retry_result, prioritized_log)[0])
            steps.append(_step("llm_retry_stronger_prompt", retry1_start, "Fallback stage 1: stronger prompt retry."))
            fallback_stage = "retry_stronger_prompt"
            if retry_classified["confidence"] >= validated["confidence"]:
                validated = retry_classified

        if should_retry(validated["confidence"]):
            retry2_start = time.perf_counter()
            simplified = _build_simplified_log(prioritized_log)
            retry_result, _, retry_usage = analyzer.analyze_log(simplified, retries=1, stronger_prompt=True)
            usage = _merge_usage(usage, retry_usage)
            retry_classified = validate_output(classifier.classify_failure(retry_result, prioritized_log)[0])
            steps.append(_step("llm_retry_summarized_log", retry2_start, "Fallback stage 2: summarized/simplified log retry."))
            fallback_stage = "retry_summarized_log"
            if retry_classified["confidence"] >= validated["confidence"]:
                validated = retry_classified

        if should_retry(validated["confidence"]):
            rule_start = time.perf_counter()
            validated, fallback_stage = _fallback_with_rules(prioritized_log, classifier)
            steps.append(_step("rule_based_classifier", rule_start, "Fallback stage 3: rule-based classification."))

    except Exception as exc:  # noqa: BLE001
        logger.warning("[WARN] LLM pipeline failed, using fallbacks: %s", exc)
        rule_start = time.perf_counter()
        validated, fallback_stage = _fallback_with_rules(prioritized_log, classifier)
        steps.append(_step("llm_analysis", llm_start, "Primary LLM analysis failed; switched to fallback.", error=str(exc)))
        steps.append(_step("rule_based_classifier", rule_start, "Fallback stage 3: rule-based classification."))

    if should_retry(validated["confidence"]):
        default_start = time.perf_counter()
        validated = validate_output(
            _safe_default(
                "Unable to confidently classify failure.",
                "Fallback stage 4: safe default response after low confidence.",
            )
        )
        fallback_stage = "safe_default"
        steps.append(_step("safe_default", default_start, "Fallback stage 4: safe default output."))

    if "reasoning" not in validated or not str(validated.get("reasoning", "")).strip():
        validated["reasoning"] = (
            f"Classified as {validated['category']} due to deterministic rule signals and extracted failure patterns."
        )

    steps.append(_step("classification", time.perf_counter(), "Classification finalized.", decision=validated["category"]))
    steps.append(_step("validation", time.perf_counter(), "Output validated.", status="passed"))

    metrics = {
        "latency": round(time.perf_counter() - overall_start, 3),
        "tokens": int(usage["total_tokens"]),
        "cost_estimate": round((usage["total_tokens"] / 1000) * _COST_PER_1K_TOKENS, 6),
    }

    output = {
        **validated,
        "steps": steps,
        "metrics": metrics,
        "fallback_stage": fallback_stage,
        "agent_version": AGENT_VERSION,
        "prompt_version": prompt_version,
        "deterministic": deterministic,
    }

    if quality["is_partial"] or quality["is_truncated"]:
        output["confidence"] = round(max(0.1, output["confidence"] - 0.1), 2)

    _CACHE[key] = output
    store_result(cleaned_log, output)
    return output


def run_batch(
    folder: Path,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
    debug: bool = False,
    deterministic: bool = False,
) -> list[dict[str, Any]]:
    if not folder.exists() or not folder.is_dir():
        raise ValueError(f"Folder does not exist or is not a directory: {folder}")

    outputs: list[dict[str, Any]] = []
    for log_file in sorted(folder.glob("*.txt")):
        result = run_analysis(log_file.read_text(encoding="utf-8"), prompt_version=prompt_version, debug=debug, deterministic=deterministic)
        outputs.append({"file": log_file.name, **result})

    avg_latency = sum(item["metrics"]["latency"] for item in outputs) / len(outputs) if outputs else 0.0
    avg_confidence = sum(item["confidence"] for item in outputs) / len(outputs) if outputs else 0.0
    avg_cost = sum(float(item["metrics"].get("cost_estimate", 0.0)) for item in outputs) / len(outputs) if outputs else 0.0
    total_cost = sum(float(item["metrics"].get("cost_estimate", 0.0)) for item in outputs)
    category_counter = Counter(item["category"] for item in outputs)
    print(json.dumps(outputs, indent=2))
    print(
        "Summary: "
        f"processed={len(outputs)} "
        f"prompt={prompt_version} "
        f"avg_confidence={avg_confidence:.2f} "
        f"avg_latency={avg_latency:.3f}s "
        f"avg_cost=${avg_cost:.4f} "
        f"total_cost=${total_cost:.4f} "
        f"category_breakdown={dict(category_counter)}"
    )
    return outputs


def build_ci_report(outputs: list[dict[str, Any]]) -> dict[str, Any]:
    summary = Counter(item["category"] for item in outputs)
    return {
        "total_logs": len(outputs),
        "failures_detected": len(outputs),
        "categories": dict(summary),
    }


def run_ci_mode(
    log_stream_file: Path,
    prompt_version: str = DEFAULT_PROMPT_VERSION,
    debug: bool = False,
    deterministic: bool = False,
) -> dict[str, Any]:
    payload = log_stream_file.read_text(encoding="utf-8")
    blocks = split_ci_log_stream(payload)
    outputs = [run_analysis(block, prompt_version=prompt_version, debug=debug, deterministic=deterministic) for block in blocks]

    summary = Counter(item["category"] for item in outputs)
    report = {
        "source": str(log_stream_file),
        "processed_logs": len(outputs),
        "category_summary": dict(summary),
        "avg_confidence": round(sum(item["confidence"] for item in outputs) / len(outputs), 3) if outputs else 0.0,
        "avg_latency": round(sum(item["metrics"]["latency"] for item in outputs) / len(outputs), 3) if outputs else 0.0,
        "avg_cost_per_log": round(sum(float(item["metrics"].get("cost_estimate", 0.0)) for item in outputs) / len(outputs), 6) if outputs else 0.0,
        "total_cost": round(sum(float(item["metrics"].get("cost_estimate", 0.0)) for item in outputs), 6),
        "results": outputs,
    }
    print(json.dumps(report, indent=2))
    return report


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze QA failures from logs using an AI agent pipeline.")
    parser.add_argument("--log", type=str, help="Inline log text to analyze.")
    parser.add_argument("--file", type=Path, help="Path to a log file to analyze.")
    parser.add_argument("--folder", type=Path, help="Folder containing .txt logs for batch analysis.")
    parser.add_argument("--ci-mode", type=Path, help="Path to CI log stream file with multiple logs.")
    parser.add_argument("--log-file", type=Path, help="Deprecated alias for --file.")
    parser.add_argument("--output", type=Path, help="Write JSON output to file.")
    parser.add_argument("--ci-report", action="store_true", help="Emit CI/CD friendly summary report.")
    parser.add_argument("--deterministic", action="store_true", help="Enable deterministic low-variance mode.")
    parser.add_argument("--prompt", type=str, default=DEFAULT_PROMPT_VERSION, help="Prompt version to use (e.g., v1, v2).")
    parser.add_argument("--debug", action="store_true", help="Enable debug traces for analyzer and classifier internals.")
    return parser.parse_args()


def _get_input_text(args: argparse.Namespace) -> str:
    if args.log:
        return args.log

    file_path = args.file or args.log_file
    if file_path:
        return file_path.read_text(encoding="utf-8")

    raise ValueError("Provide input via --log or --file.")


def _write_json_output(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main() -> None:
    args = _parse_args()
    logging.basicConfig(level=logging.INFO if args.debug else logging.WARNING, format="%(message)s")
    try:
        if args.folder:
            outputs = run_batch(args.folder, prompt_version=args.prompt, debug=args.debug, deterministic=args.deterministic)
            rendered: Any = build_ci_report(outputs) if args.ci_report else outputs
            if args.output:
                _write_json_output(args.output, rendered)
            elif args.ci_report:
                print(json.dumps(rendered, indent=2))
            return

        if args.ci_mode:
            report = run_ci_mode(args.ci_mode, prompt_version=args.prompt, debug=args.debug, deterministic=args.deterministic)
            rendered = build_ci_report(report["results"]) if args.ci_report else report
            if args.output:
                _write_json_output(args.output, rendered)
            elif args.ci_report:
                print(json.dumps(rendered, indent=2))
            return

        result = run_analysis(_get_input_text(args), prompt_version=args.prompt, debug=args.debug, deterministic=args.deterministic)
        if args.output:
            _write_json_output(args.output, result)
        print(json.dumps(result, indent=2))
    except Exception as exc:  # noqa: BLE001
        logger.error("[ERROR] Analysis failed: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
