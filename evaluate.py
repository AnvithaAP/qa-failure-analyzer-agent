"""Run end-to-end evaluation against sample QA logs."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from agent import run_analysis
from src.classifier import infer_category_from_rules
from src.evaluator import evaluate

LOG_DIR = Path("examples/logs")

EXPECTED = {
    "timeout.txt": "Environment Issue",
    "assertion.txt": "Test Issue",
    "locator.txt": "Test Issue",
    "api_error.txt": "Product Bug",
    "db_failure.txt": "Environment Issue",
}


def _accuracy(items: list[tuple[str, str]]) -> float:
    if not items:
        return 0.0
    correct = sum(1 for predicted, expected in items if predicted == expected)
    return correct / len(items)


def main() -> None:
    predictions: list[dict[str, object]] = []
    baseline_predictions: list[tuple[str, str]] = []
    llm_predictions: list[tuple[str, str]] = []
    ground_truth: list[dict[str, object]] = []

    for filename, expected_category in EXPECTED.items():
        log_path = LOG_DIR / filename
        log_text = log_path.read_text(encoding="utf-8")
        result = run_analysis(log_text)

        predictions.append(result)
        ground_truth.append({"category": expected_category, "log": log_text})

        llm_predictions.append((str(result["category"]), expected_category))
        baseline = infer_category_from_rules(log_text) or "Test Issue"
        baseline_predictions.append((baseline, expected_category))

        print(
            f"- {filename}: predicted={result['category']} "
            f"expected={expected_category} confidence={result['confidence']:.2f} "
            f"latency={result['latency']:.3f}s prompt={result['prompt_version']} "
            f"tokens={result.get('token_estimate', 0)} cost=${float(result.get('cost_estimate_usd', 0.0)):.4f}"
        )

    metrics = evaluate(predictions, ground_truth)
    baseline_accuracy = _accuracy(baseline_predictions)
    llm_accuracy = _accuracy(llm_predictions)
    delta = llm_accuracy - baseline_accuracy
    total_cost = sum(float(item.get("cost_estimate_usd", 0.0)) for item in predictions)
    avg_cost = total_cost / len(predictions) if predictions else 0.0

    print("\nEvaluation Results:")
    print(f"Baseline Accuracy (rule-only): {baseline_accuracy:.0%}")
    print(f"LLM Agent Accuracy: {llm_accuracy:.0%}")
    print(f"Improvement: {delta:+.0%}")
    print(f"Overall Accuracy: {metrics['accuracy']:.0%}")
    print(f"Product Bug Accuracy: {metrics['per_category_accuracy']['Product Bug']:.0%}")
    print(f"Test Issue Accuracy: {metrics['per_category_accuracy']['Test Issue']:.0%}")
    print(f"Environment Issue Accuracy: {metrics['per_category_accuracy']['Environment Issue']:.0%}")
    print(f"Avg Confidence: {metrics['avg_confidence']:.2f}")
    print(f"Avg Latency: {metrics['avg_latency']:.3f} seconds")
    print(f"Avg Cost per log: ${avg_cost:.4f}")
    print(f"Total Evaluation Cost: ${total_cost:.4f}")

    print("\nPrecision/Recall by Category:")
    for category, values in metrics["precision_recall"].items():
        print(f"- {category}: precision={values['precision']:.2f}, recall={values['recall']:.2f}")

    print("\nMisclassifications:")
    if metrics["misclassifications"]:
        for item in metrics["misclassifications"]:
            print(f"Log: {item['log']}")
            print(f"Expected: {item['expected']}")
            print(f"Predicted: {item['predicted']}")
            print("Reason:")
            print(f"- {item['reason']}")
            print()
    else:
        print("- None")

    if metrics["top_failure_patterns"]:
        print("Top Failure Patterns:")
        for pattern in metrics["top_failure_patterns"]:
            print(f"- {pattern['pattern']} (count={pattern['count']})")

    if metrics["hardest_cases"]:
        print("\nHardest Cases:")
        for case in metrics["hardest_cases"]:
            print(f"- #{case['index']} {case['expected']} -> {case['predicted']} | reason={case['reason']}")

    if metrics["confusion"]:
        print("\nConfusion Totals:")
        for key, value in sorted(metrics["confusion"].items()):
            print(f"- {key}: {value}")


if __name__ == "__main__":
    main()
