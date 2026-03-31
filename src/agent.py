"""CLI and programmatic entrypoint for QA Failure Analyzer Agent."""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from classifier import classify_failure, validate_output
from llm import analyze_log
from utils import clean_log

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("qa_failure_analyzer")

_CONFIDENCE_WARNING_THRESHOLD = 0.6
_CACHE: dict[str, dict[str, Any]] = {}


def _cache_key(log_text: str) -> str:
    return hashlib.sha256(log_text.encode("utf-8")).hexdigest()


def run_analysis(log_text: str) -> dict[str, Any]:
    """Pipeline: clean -> analyze -> classify -> validate -> output."""
    if not log_text or not log_text.strip():
        raise ValueError("Log text is empty. Provide --log or --file with content.")

    logger.info("[INFO] Cleaning logs")
    cleaned_log = clean_log(log_text)

    key = _cache_key(cleaned_log)
    if key in _CACHE:
        logger.info("[INFO] Using cached response")
        return _CACHE[key]

    llm_result = analyze_log(cleaned_log, retries=1)

    logger.info("[INFO] Classifying failure")
    classified = classify_failure(llm_result, cleaned_log)

    logger.info("[INFO] Validation complete")
    validated = validate_output(classified)

    if validated["confidence"] < _CONFIDENCE_WARNING_THRESHOLD:
        logger.warning(
            "[WARN] Low-confidence analysis (%.2f). Consider manual review.", validated["confidence"]
        )

    _CACHE[key] = validated
    return validated


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze QA failures from logs using an AI agent pipeline.")
    parser.add_argument("--log", type=str, help="Inline log text to analyze.")
    parser.add_argument("--file", type=Path, help="Path to a log file to analyze.")
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
        result = run_analysis(_get_input_text(args))
        print(json.dumps(result, indent=2))
    except Exception as exc:  # noqa: BLE001
        logger.error("[ERROR] Analysis failed: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
