"""Stress tests for QA Failure Analyzer Agent robustness."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

__test__ = False

ROOT = Path(__file__).resolve().parent
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from agent import run_analysis


def _run_case(name: str, log_text: str) -> tuple[bool, str]:
    try:
        result = run_analysis(log_text, deterministic=True)
        passed = isinstance(result, dict) and "category" in result and "steps" in result
        return passed, f"category={result.get('category')} confidence={result.get('confidence')}"
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)


def main() -> None:
    cases: dict[str, str] = {
        "very_large_log": ("ERROR Timeout while connecting\n" * 20000),
        "empty_log": "   ",
        "random_noise": "zxqv 123 ### ???\\n" * 500,
        "multiple_errors": "ERROR Timeout reached\\nAssertionError expected 1 got 2\\nHTTP 500 Internal Server Error",
    }

    summary: list[dict[str, Any]] = []
    for name, payload in cases.items():
        ok, details = _run_case(name, payload)
        summary.append({"case": name, "status": "PASS" if ok else "FAIL", "details": details})

    passed = sum(1 for item in summary if item["status"] == "PASS")
    print("Stress test summary")
    for item in summary:
        print(f"- {item['case']}: {item['status']} ({item['details']})")
    print(f"Result: {passed}/{len(summary)} passed")


if __name__ == "__main__":
    main()
