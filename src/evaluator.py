"""Evaluation helpers for the QA failure analyzer agent."""

from __future__ import annotations

from typing import Any


def evaluate(predictions: list[dict[str, Any]], ground_truth: list[dict[str, Any]]) -> dict[str, float | int]:
    """Compute classification accuracy and average confidence."""
    if len(predictions) != len(ground_truth):
        raise ValueError("Predictions and ground truth must have same length.")

    total = len(predictions)
    if total == 0:
        return {"accuracy": 0.0, "avg_confidence": 0.0, "correct": 0, "total": 0}

    correct = 0
    confidence_sum = 0.0

    for prediction, truth in zip(predictions, ground_truth, strict=True):
        if prediction.get("category") == truth.get("category"):
            correct += 1
        confidence_sum += float(prediction.get("confidence", 0.0))

    return {
        "accuracy": correct / total,
        "avg_confidence": confidence_sum / total,
        "correct": correct,
        "total": total,
    }
