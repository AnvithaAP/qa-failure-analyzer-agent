"""Run end-to-end evaluation against sample QA logs."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC_PATH = ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from agent import run_analysis
from src.classifier import infer_category_from_rules
from src.evaluator import CATEGORIES, evaluate

DATASET_PATH = Path("examples/eval_dataset.json")


def _accuracy(items: list[tuple[str, str]]) -> float:
    if not items:
        return 0.0
    correct = sum(1 for predicted, expected in items if predicted == expected)
    return correct / len(items)


def _load_dataset() -> list[dict[str, str]]:
    payload = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        raise ValueError("examples/eval_dataset.json must be a list of objects.")
    dataset: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        file_path = str(item.get("file", "")).strip()
        category = str(item.get("category", "")).strip()
        if file_path and category:
            dataset.append({"file": file_path, "category": category})
    if not dataset:
        raise ValueError("Evaluation dataset is empty.")
    return dataset


def main() -> None:
    predictions: list[dict[str, object]] = []
    baseline_predictions: list[tuple[str, str]] = []
    llm_predictions: list[tuple[str, str]] = []
    ground_truth: list[dict[str, object]] = []

    for entry in _load_dataset():
        log_path = Path(entry["file"])
        expected_category = entry["category"]
        log_text = log_path.read_text(encoding="utf-8")
        result = run_analysis(log_text)

        predictions.append(result)
        ground_truth.append({"category": expected_category, "log": log_text})

        llm_predictions.append((str(result["category"]), expected_category))
        baseline = infer_category_from_rules(log_text) or "Test Issue"
        baseline_predictions.append((baseline, expected_category))

        metrics = result.get("metrics", {})
        print(
            f"- {log_path.name}: predicted={result['category']} "
            f"expected={expected_category} confidence={result['confidence']:.2f} "
            f"latency={float(metrics.get('latency', 0.0)):.3f}s prompt={result['prompt_version']} "
            f"tokens={int(metrics.get('tokens', 0))} cost=${float(metrics.get('cost_estimate', 0.0)):.4f}"
        )

    metrics = evaluate(predictions, ground_truth)
    baseline_accuracy = _accuracy(baseline_predictions)
    llm_accuracy = _accuracy(llm_predictions)
    delta = llm_accuracy - baseline_accuracy
    total_cost = sum(float(item.get("metrics", {}).get("cost_estimate", 0.0)) for item in predictions)
    avg_cost = total_cost / len(predictions) if predictions else 0.0

    print("\nEvaluation Results:")
    print(f"Dataset Size: {len(predictions)}")
    print(f"Baseline Accuracy (rule-only): {baseline_accuracy:.0%}")
    print(f"LLM Agent Accuracy: {llm_accuracy:.0%}")
    print(f"Improvement: {delta:+.0%}")
    print(f"Overall Accuracy: {metrics['accuracy']:.0%}")
    for category in CATEGORIES:
        print(f"{category} Accuracy: {metrics['per_category_accuracy'][category]:.0%}")
    print(f"Avg Confidence: {metrics['avg_confidence']:.2f}")
    print(f"Avg Latency: {metrics['avg_latency']:.3f} seconds")
    print(f"Avg Cost per log: ${avg_cost:.4f}")
    print(f"Total Evaluation Cost: ${total_cost:.4f}")

    print("\nPrecision/Recall by Category:")
    for category, values in metrics["precision_recall"].items():
        print(f"- {category}: precision={values['precision']:.2f}, recall={values['recall']:.2f}")


if __name__ == "__main__":
    main()
