"""Evaluation helpers for the QA failure analyzer agent."""

from __future__ import annotations

from collections import defaultdict
from typing import Any

CATEGORIES = ("Product Bug", "Test Issue", "Environment Issue")


def evaluate(predictions: list[dict[str, Any]], ground_truth: list[dict[str, Any]]) -> dict[str, Any]:
    """Compute overall/per-category metrics, confusion tracking, and latency stats."""
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
            "misclassifications": [],
            "confusion": {},
            "confusion_matrix": {category: {inner: 0 for inner in CATEGORIES} for category in CATEGORIES},
        }

    correct = 0
    confidence_sum = 0.0
    latency_sum = 0.0
    counts: dict[str, dict[str, int]] = {
        category: {"correct": 0, "total": 0} for category in CATEGORIES
    }
    misclassifications: list[dict[str, Any]] = []
    confusion: dict[str, int] = defaultdict(int)
    confusion_matrix: dict[str, dict[str, int]] = {
        category: {inner: 0 for inner in CATEGORIES} for category in CATEGORIES
    }

    for index, (prediction, truth) in enumerate(zip(predictions, ground_truth, strict=True), start=1):
        predicted_category = str(prediction.get("category", ""))
        expected_category = str(truth.get("category", ""))
        matched = predicted_category == expected_category
        if expected_category in CATEGORIES and predicted_category in CATEGORIES:
            confusion_matrix[expected_category][predicted_category] += 1

        if expected_category in counts:
            counts[expected_category]["total"] += 1
            if matched:
                counts[expected_category]["correct"] += 1

        if matched:
            correct += 1
        else:
            misclassifications.append(
                {
                    "index": index,
                    "expected": expected_category,
                    "predicted": predicted_category,
                }
            )
            confusion[f"{expected_category} -> {predicted_category}"] += 1

        confidence_sum += float(prediction.get("confidence", 0.0))
        latency_sum += float(prediction.get("latency", 0.0))

    per_category_accuracy = {
        category: (
            counts[category]["correct"] / counts[category]["total"]
            if counts[category]["total"]
            else 0.0
        )
        for category in CATEGORIES
    }

    return {
        "accuracy": correct / total,
        "avg_confidence": confidence_sum / total,
        "avg_latency": latency_sum / total,
        "correct": correct,
        "total": total,
        "per_category_accuracy": per_category_accuracy,
        "misclassifications": misclassifications,
        "confusion": dict(confusion),
        "confusion_matrix": confusion_matrix,
    }
