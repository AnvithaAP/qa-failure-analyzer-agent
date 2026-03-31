"""Run end-to-end evaluation against sample QA logs."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from agent import run_analysis
from src.evaluator import evaluate

LOG_DIR = Path("examples/logs")

EXPECTED = {
    "timeout.txt": "Environment Issue",
    "assertion.txt": "Test Issue",
    "locator.txt": "Test Issue",
    "api_error.txt": "Product Bug",
    "db_failure.txt": "Environment Issue",
}


def main() -> None:
    predictions: list[dict[str, object]] = []
    ground_truth: list[dict[str, object]] = []

    for filename, expected_category in EXPECTED.items():
        log_path = LOG_DIR / filename
        log_text = log_path.read_text(encoding="utf-8")
        result = run_analysis(log_text)
        predictions.append(result)
        ground_truth.append({"category": expected_category})

        print(
            f"- {filename}: predicted={result['category']} "
            f"expected={expected_category} confidence={result['confidence']:.2f} "
            f"latency={result['latency']:.3f}s"
        )

    metrics = evaluate(predictions, ground_truth)
    print("\nEvaluation Results:")
    print(f"Overall Accuracy: {metrics['accuracy']:.0%}")
    print(f"Product Bug Accuracy: {metrics['per_category_accuracy']['Product Bug']:.0%}")
    print(f"Test Issue Accuracy: {metrics['per_category_accuracy']['Test Issue']:.0%}")
    print(f"Environment Issue Accuracy: {metrics['per_category_accuracy']['Environment Issue']:.0%}")
    print(f"Avg Confidence: {metrics['avg_confidence']:.2f}")
    print(f"Avg Latency: {metrics['avg_latency']:.3f} seconds")

    print("\nMisclassifications:")
    if metrics["misclassifications"]:
        for item in metrics["misclassifications"]:
            print(
                f"- Log {item['index']}: Expected {item['expected']} -> "
                f"Predicted {item['predicted']}"
            )
    else:
        print("- None")


if __name__ == "__main__":
    main()
