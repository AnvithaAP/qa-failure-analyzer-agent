"""CLI and programmatic entrypoint for QA Failure Analyzer Agent."""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from classifier import postprocess_analysis
from llm import analyze_log
from utils import clean_log_text, truncate_log

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("qa_failure_analyzer")


def run_analysis(log_text: str) -> dict[str, Any]:
    """Run the full pipeline: clean -> truncate -> LLM -> normalize."""
    if not log_text or not log_text.strip():
        raise ValueError("Log text is empty. Provide --log or --log-file with content.")

    cleaned = clean_log_text(log_text)
    prepared = truncate_log(cleaned)
    raw_output = analyze_log(prepared)
    return postprocess_analysis(raw_output)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze QA failures from logs using an LLM.")
    parser.add_argument("--log", type=str, help="Inline log text to analyze.")
    parser.add_argument("--log-file", type=Path, help="Path to a log file to analyze.")
    return parser.parse_args()


def _get_input_text(args: argparse.Namespace) -> str:
    if args.log:
        return args.log
    if args.log_file:
        return args.log_file.read_text(encoding="utf-8")
    raise ValueError("Provide input via --log or --log-file.")


def main() -> None:
    args = _parse_args()

    try:
        input_text = _get_input_text(args)
        result = run_analysis(input_text)
        print(json.dumps(result, indent=2))
    except Exception as exc:  # noqa: BLE001 - user-facing CLI boundary
        logger.error("Analysis failed: %s", exc)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
