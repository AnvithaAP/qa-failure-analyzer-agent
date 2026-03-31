"""Evaluator role for QA failure analyzer metrics and introspection."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

CATEGORIES = ("Product Bug", "Test Issue", "Environment Issue")


def _short_log(log_text: str, max_len: int = 120) -> str:
    one_line = " ".join(log_text.split())
    if len(one_line) <= max_len:
        return one_line
    return f"{one_line[:max_len].rstrip()}..."


def _reason_for_misclassification(log_text: str, expected: str, predicted: str) -> str:
    lowered = log_text.lower()
    if "timeout" in lowered and "assert" in lowered:
        return "Mixed signals (timeout + assertion) increased ambiguity."
    if "timeout" in lowered and predicted == "Test Issue":
        return "Likely confusion due to keyword overlap ('timeout' vs assertion/test cues)."
    if "assert" in lowered and predicted == "Product Bug":
        return "Assertion signal may have been interpreted as product defect severity."
    if "connection" in lowered and predicted == "Test Issue":
        return "Environment/network cues were likely underweighted against test-step wording."
    return f"Boundary between {expected} and {predicted} appears ambiguous from this log snippet."


def evaluate(predictions: list[dict[str, Any]], ground_truth: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute overall/per-category metrics plus failure-pattern introspection."""
    if len(predictions) != len(ground_truth):
        raise ValueError("Predictions and ground truth must have same length.")

    total = len(predictions)
    if total == 0:
        return {
            "accuracy": 0.0,
            "avg_confidence": 0.0,
            "avg_latency": 0.0,
            "correct": 0,
            "total": 0,
            "per_category_accuracy": {category: 0.0 for category in CATEGORIES},
            "precision_recall": {category: {"precision": 0.0, "recall": 0.0} for category in CATEGORIES},
            "misclassifications": [],
            "confusion": {},
            "confusion_matrix": {category: {inner: 0 for inner in CATEGORIES} for category in CATEGORIES},
            "top_failure_patterns": [],
            "hardest_cases": [],
        }

    correct = 0
    confidence_sum = 0.0
    latency_sum = 0.0
    counts: dict[str, dict[str, int]] = {category: {"correct": 0, "total": 0} for category in CATEGORIES}
    tp = {category: 0 for category in CATEGORIES}
    fp = {category: 0 for category in CATEGORIES}
    fn = {category: 0 for category in CATEGORIES}

    misclassifications: list[dict[str, Any]] = []
    confusion: dict[str, int] = defaultdict(int)
    confusion_matrix: dict[str, dict[str, int]] = {
        category: {inner: 0 for inner in CATEGORIES} for category in CATEGORIES
    }

    for index, (prediction, truth) in enumerate(zip(predictions, ground_truth, strict=True), start=1):
        predicted_category = str(prediction.get("category", ""))
        expected_category = str(truth.get("category", ""))
        log_text = str(truth.get("log", ""))
        matched = predicted_category == expected_category
        if expected_category in CATEGORIES and predicted_category in CATEGORIES:
            confusion_matrix[expected_category][predicted_category] += 1

        if expected_category in counts:
            counts[expected_category]["total"] += 1
            if matched:
                counts[expected_category]["correct"] += 1

        for category in CATEGORIES:
            if predicted_category == category and expected_category == category:
                tp[category] += 1
            elif predicted_category == category and expected_category != category:
                fp[category] += 1
            elif predicted_category != category and expected_category == category:
                fn[category] += 1

        if matched:
            correct += 1
        else:
            misclassifications.append(
                {
                    "index": index,
                    "log": _short_log(log_text),
                    "expected": expected_category,
                    "predicted": predicted_category,
                    "reason": _reason_for_misclassification(log_text, expected_category, predicted_category),
                    "confidence": float(prediction.get("confidence", 0.0)),
                }
            )
            confusion[f"{expected_category} -> {predicted_category}"] += 1

        confidence_sum += float(prediction.get("confidence", 0.0))
        latency_sum += float(prediction.get("latency", 0.0))

    per_category_accuracy = {
        category: (counts[category]["correct"] / counts[category]["total"] if counts[category]["total"] else 0.0)
        for category in CATEGORIES
    }

    precision_recall = {}
    for category in CATEGORIES:
        precision = tp[category] / (tp[category] + fp[category]) if (tp[category] + fp[category]) else 0.0
        recall = tp[category] / (tp[category] + fn[category]) if (tp[category] + fn[category]) else 0.0
        precision_recall[category] = {"precision": precision, "recall": recall}

    top_failure_patterns = [
        {"pattern": pattern, "count": count}
        for pattern, count in Counter(item["reason"] for item in misclassifications).most_common(3)
    ]

    hardest_cases = sorted(misclassifications, key=lambda item: item["confidence"], reverse=True)[:3]

    return {
        "accuracy": correct / total,
        "avg_confidence": confidence_sum / total,
        "avg_latency": latency_sum / total,
        "correct": correct,
        "total": total,
        "per_category_accuracy": per_category_accuracy,
        "precision_recall": precision_recall,
        "misclassifications": misclassifications,
        "confusion": dict(confusion),
        "confusion_matrix": confusion_matrix,
        "top_failure_patterns": top_failure_patterns,
        "hardest_cases": hardest_cases,
    }
