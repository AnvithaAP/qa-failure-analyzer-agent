"""Post-processing and validation for model output."""

from __future__ import annotations

from typing import Any

_ALLOWED_CATEGORIES = {"Product Bug", "Test Issue", "Environment Issue"}
_CATEGORY_NORMALIZATION = {
    "product": "Product Bug",
    "product bug": "Product Bug",
    "bug": "Product Bug",
    "test": "Test Issue",
    "test issue": "Test Issue",
    "flaky test": "Test Issue",
    "environment": "Environment Issue",
    "env": "Environment Issue",
    "environment issue": "Environment Issue",
    "infra": "Environment Issue",
}


def _normalize_category(category: str) -> str:
    lowered = category.strip().lower()
    if category in _ALLOWED_CATEGORIES:
        return category
    if lowered in _CATEGORY_NORMALIZATION:
        return _CATEGORY_NORMALIZATION[lowered]
    return "Test Issue"


def _normalize_confidence(confidence: Any) -> float:
    try:
        numeric = float(confidence)
    except (TypeError, ValueError):
        return 0.5

    return max(0.0, min(1.0, numeric))


def postprocess_analysis(result: dict[str, Any]) -> dict[str, Any]:
    """Guarantee output shape and normalized values."""
    root_cause = str(result.get("root_cause") or "Unable to determine from provided log.").strip()
    category = _normalize_category(str(result.get("category") or ""))
    confidence = _normalize_confidence(result.get("confidence"))
    suggestion = str(result.get("suggestion") or "Collect additional logs and retry analysis.").strip()

    return {
        "root_cause": root_cause,
        "category": category,
        "confidence": confidence,
        "suggestion": suggestion,
    }
