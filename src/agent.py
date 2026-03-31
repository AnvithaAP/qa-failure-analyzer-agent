"""CLI and programmatic entrypoint for QA Failure Analyzer Agent."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from classifier import classify_failure, validate_output
from llm import analyze_log, summarize_log
from memory import retrieve_similar, store_result
from utils import clean_log

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("qa_failure_analyzer")

_CONFIDENCE_WARNING_THRESHOLD = 0.6
_LARGE_LOG_THRESHOLD = 800
_CACHE: dict[str, dict[str, Any]] = {}


def _cache_key(log_text: str) -> str:
    return hashlib.sha256(log_text.encode("utf-8")).hexdigest()


def should_retry(confidence: float) -> bool:
    return confidence < _CONFIDENCE_WARNING_THRESHOLD


def _analyze_with_adaptive_logic(cleaned_log: str) -> tuple[dict[str, Any], bool]:
    use_summary = len(cleaned_log) > _LARGE_LOG_THRESHOLD
    logger.info("[INFO] Log length: %s chars", len(cleaned_log))
    logger.info("[INFO] Using summarization: %s", "YES" if use_summary else "NO")

    analysis_input = cleaned_log
    if use_summary:
        analysis_input = summarize_log(cleaned_log)

    llm_result = analyze_log(analysis_input, retries=1)
    classified = validate_output(classify_failure(llm_result, cleaned_log))

    if should_retry(classified["confidence"]):
        logger.info("[INFO] LLM confidence: %.2f → RETRY triggered", classified["confidence"])
        retry_input = analysis_input if use_summary else clean_log(cleaned_log)
        retry_result = analyze_log(retry_input, retries=1, stronger_prompt=True)
        retry_classified = validate_output(classify_failure(retry_result, cleaned_log))
        if retry_classified["confidence"] >= classified["confidence"]:
            classified = retry_classified
    return classified, use_summary


def run_analysis(log_text: str) -> dict[str, Any]:
    """Pipeline: clean -> (optional summarize) -> analyze -> classify -> validate -> output."""
    if not log_text or not log_text.strip():
        raise ValueError("Log text is empty. Provide --log or --file with content.")

    logger.info("[INFO] Cleaning logs")
    cleaned_log = clean_log(log_text)

    memory_hit = retrieve_similar(cleaned_log)
    if memory_hit:
        logger.info("[INFO] Similar log found in memory; reusing previous classification")
        return validate_output(memory_hit)

    key = _cache_key(cleaned_log)
    if key in _CACHE:
        logger.info("[INFO] Using cached response")
        return _CACHE[key]

    start = time.perf_counter()
    validated, _ = _analyze_with_adaptive_logic(cleaned_log)
    validated["latency"] = round(time.perf_counter() - start, 3)

    if should_retry(validated["confidence"]):
        logger.warning("[WARN] Low-confidence analysis (%.2f). Consider manual review.", validated["confidence"])

    logger.info("[INFO] Final classification: %s", validated["category"])
    logger.info("[INFO] Latency: %.3f seconds", validated["latency"])

    _CACHE[key] = validated
    store_result(cleaned_log, validated)
    return validated


def run_batch(folder: Path) -> list[dict[str, Any]]:
    """Process all text logs in a folder and return standardized outputs."""
    if not folder.exists() or not folder.is_dir():
        raise ValueError(f"Folder does not exist or is not a directory: {folder}")

    outputs: list[dict[str, Any]] = []
    for log_file in sorted(folder.glob("*.txt")):
        result = run_analysis(log_file.read_text(encoding="utf-8"))
        result_with_file = {"file": log_file.name, **result}
        outputs.append(result_with_file)

    avg_latency = sum(item["latency"] for item in outputs) / len(outputs) if outputs else 0.0
    print(json.dumps(outputs, indent=2))
    print(f"Processed {len(outputs)} logs. Average latency: {avg_latency:.3f} seconds")
    return outputs


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze QA failures from logs using an AI agent pipeline.")
    parser.add_argument("--log", type=str, help="Inline log text to analyze.")
    parser.add_argument("--file", type=Path, help="Path to a log file to analyze.")
    parser.add_argument("--folder", type=Path, help="Folder containing .txt logs for batch analysis.")
    parser.add_argument("--log-file", type=Path, help="Deprecated alias for --file.")
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
    try:
        if args.folder:
            run_batch(args.folder)
            return

        result = run_analysis(_get_input_text(args))
        print(json.dumps(result, indent=2))
    except Exception as exc:  # noqa: BLE001
        logger.error("[ERROR] Analysis failed: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
