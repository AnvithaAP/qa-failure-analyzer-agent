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
from utils import assess_log_quality, clean_log, detect_error_events, split_ci_log_stream

logger = logging.getLogger("qa_failure_analyzer")

_CONFIDENCE_WARNING_THRESHOLD = 0.6
_LARGE_LOG_THRESHOLD = 800
_SIMPLIFIED_LOG_CHARS = 500
_CACHE: dict[str, dict[str, Any]] = {}

# Rough estimate for gpt-4o-mini blended I/O cost.
_COST_PER_1K_TOKENS = 0.0005


def _cache_key(log_text: str, prompt_version: str) -> str:
    payload = f"{prompt_version}:{log_text}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def should_retry(confidence: float) -> bool:
    return confidence < _CONFIDENCE_WARNING_THRESHOLD


def _build_simplified_log(log_text: str, max_chars: int = _SIMPLIFIED_LOG_CHARS) -> str:
    """Build a compact signal-first log for fallback retries."""
    lines = [line.strip() for line in log_text.splitlines() if line.strip()]
    signal_lines = [
        line
        for line in lines
        if any(token in line.lower() for token in ("error", "exception", "failed", "timeout"))
    ]
    candidate = "\n".join(signal_lines or lines)
    return candidate[:max_chars]


def _pick_critical_error(cleaned_log: str) -> str:
    events = detect_error_events(cleaned_log)
    if not events:
        return cleaned_log

    prioritized = sorted(
        events,
        key=lambda event: (infer_rule_signal(event) or {"severity": 0})["severity"],
        reverse=True,
    )
    return prioritized[0]


def _confidence_reason(
    existing_reason: str,
    log_quality: dict[str, Any],
    used_rule_override: bool,
) -> str:
    notes = [existing_reason.strip() or "Confidence based on model output."]
    if used_rule_override:
        notes.append("Rule override increased certainty.")
    if log_quality["multi_error"]:
        notes.append("Multiple errors detected; highest-severity signal prioritized.")
    if log_quality["is_truncated"] or log_quality["is_partial"]:
        notes.append("Log appears partial/truncated; confidence penalized.")
    return " ".join(notes)


def _analyze_with_adaptive_logic(
    cleaned_log: str,
    analyzer: Analyzer,
    classifier: Classifier,
) -> tuple[dict[str, Any], bool, dict[str, float]]:
    log_quality = assess_log_quality(cleaned_log)
    prioritized_log = _pick_critical_error(cleaned_log) if log_quality["multi_error"] else cleaned_log

    use_summary = len(prioritized_log) > _LARGE_LOG_THRESHOLD
    logger.info("[INFO] Log length: %s chars", len(prioritized_log))
    logger.info("[INFO] Using summarization: %s", "YES" if use_summary else "NO")

    analysis_input = analyzer.summarize_log(prioritized_log) if use_summary else prioritized_log

    llm_result, _, usage = analyzer.analyze_log(analysis_input, retries=1)
    classified, adjustment = classifier.classify_failure(llm_result, prioritized_log)
    classified = validate_output(classified)

    if should_retry(classified["confidence"]):
        logger.info("[INFO] LLM confidence: %.2f → RETRY triggered", classified["confidence"])
        retry_input = _build_simplified_log(analysis_input if use_summary else prioritized_log)
        retry_result, _, retry_usage = analyzer.analyze_log(retry_input, retries=1, stronger_prompt=True)
        usage = {
            "prompt_tokens": usage["prompt_tokens"] + retry_usage["prompt_tokens"],
            "completion_tokens": usage["completion_tokens"] + retry_usage["completion_tokens"],
            "total_tokens": usage["total_tokens"] + retry_usage["total_tokens"],
        }
        retry_classified, retry_adjustment = classifier.classify_failure(retry_result, prioritized_log)
        retry_classified = validate_output(retry_classified)
        if retry_classified["confidence"] >= classified["confidence"]:
            classified = retry_classified
            adjustment = retry_adjustment

    if log_quality["is_partial"] or log_quality["is_truncated"]:
        classified["confidence"] = round(max(0.1, classified["confidence"] - 0.1), 2)

    classified["confidence_reason"] = _confidence_reason(
        classified.get("confidence_reason", ""),
        log_quality=log_quality,
        used_rule_override=bool(adjustment),
    )
    return classified, use_summary, usage


def run_analysis(log_text: str, prompt_version: str = DEFAULT_PROMPT_VERSION, debug: bool = False) -> dict[str, Any]:
    """Pipeline: clean -> optional summarize -> analyze -> classify -> validate -> output."""
    if not log_text or not log_text.strip():
        raise ValueError("Log text is empty. Provide --log or --file with content.")

    logger.info("[INFO] Cleaning logs")
    cleaned_log = clean_log(log_text)

    memory_hit = retrieve_similar(cleaned_log)
    if memory_hit:
        logger.info("[INFO] Similar log found in memory; reusing previous classification")
        out = validate_output(memory_hit)
        out["prompt_version"] = prompt_version
        out.setdefault("confidence_reason", "Reused high-similarity prior decision from memory.")
        return out

    key = _cache_key(cleaned_log, prompt_version)
    if key in _CACHE:
        logger.info("[INFO] Using cached response")
        return _CACHE[key]

    analyzer = Analyzer(prompt_version=prompt_version, debug=debug)
    classifier = Classifier(debug=debug)

    start = time.perf_counter()
    validated, _, usage = _analyze_with_adaptive_logic(cleaned_log, analyzer=analyzer, classifier=classifier)
    validated["latency"] = round(time.perf_counter() - start, 3)
    validated["prompt_version"] = prompt_version
    validated["token_estimate"] = usage["total_tokens"]
    validated["cost_estimate_usd"] = round((usage["total_tokens"] / 1000) * _COST_PER_1K_TOKENS, 6)

    if should_retry(validated["confidence"]):
        logger.warning("[WARN] Low-confidence analysis (%.2f). Consider manual review.", validated["confidence"])

    logger.info("[INFO] Final classification: %s", validated["category"])
    logger.info("[INFO] Latency: %.3f seconds", validated["latency"])

    _CACHE[key] = validated
    store_result(cleaned_log, validated)
    return validated


def run_batch(folder: Path, prompt_version: str = DEFAULT_PROMPT_VERSION, debug: bool = False) -> list[dict[str, Any]]:
    """Process all text logs in a folder and return standardized outputs."""
    if not folder.exists() or not folder.is_dir():
        raise ValueError(f"Folder does not exist or is not a directory: {folder}")

    outputs: list[dict[str, Any]] = []
    for log_file in sorted(folder.glob("*.txt")):
        result = run_analysis(log_file.read_text(encoding="utf-8"), prompt_version=prompt_version, debug=debug)
        result_with_file = {"file": log_file.name, **result}
        outputs.append(result_with_file)

    avg_latency = sum(item["latency"] for item in outputs) / len(outputs) if outputs else 0.0
    avg_confidence = sum(item["confidence"] for item in outputs) / len(outputs) if outputs else 0.0
    avg_cost = sum(float(item.get("cost_estimate_usd", 0.0)) for item in outputs) / len(outputs) if outputs else 0.0
    total_cost = sum(float(item.get("cost_estimate_usd", 0.0)) for item in outputs)
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


def run_ci_mode(log_stream_file: Path, prompt_version: str = DEFAULT_PROMPT_VERSION, debug: bool = False) -> dict[str, Any]:
    """Process a CI log stream with multiple failure blocks and return a structured report."""
    payload = log_stream_file.read_text(encoding="utf-8")
    blocks = split_ci_log_stream(payload)
    outputs = [run_analysis(block, prompt_version=prompt_version, debug=debug) for block in blocks]

    summary = Counter(item["category"] for item in outputs)
    report = {
        "source": str(log_stream_file),
        "processed_logs": len(outputs),
        "category_summary": dict(summary),
        "avg_confidence": round(sum(item["confidence"] for item in outputs) / len(outputs), 3) if outputs else 0.0,
        "avg_latency": round(sum(item["latency"] for item in outputs) / len(outputs), 3) if outputs else 0.0,
        "avg_cost_per_log": round(sum(float(item.get("cost_estimate_usd", 0.0)) for item in outputs) / len(outputs), 6) if outputs else 0.0,
        "total_cost": round(sum(float(item.get("cost_estimate_usd", 0.0)) for item in outputs), 6),
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


def main() -> None:
    args = _parse_args()
    logging.basicConfig(level=logging.INFO if args.debug else logging.WARNING, format="%(message)s")
    try:
        if args.folder:
            run_batch(args.folder, prompt_version=args.prompt, debug=args.debug)
            return
        if args.ci_mode:
            run_ci_mode(args.ci_mode, prompt_version=args.prompt, debug=args.debug)
            return

        result = run_analysis(_get_input_text(args), prompt_version=args.prompt, debug=args.debug)
        print(json.dumps(result, indent=2))
    except Exception as exc:  # noqa: BLE001
        logger.error("[ERROR] Analysis failed: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
