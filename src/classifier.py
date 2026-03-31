"""Post-processing, rule-based classification, and validation for model output."""

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

_RULES: list[tuple[str, str]] = [
    ("timeout", "Environment Issue"),
    ("timed out", "Environment Issue"),
    ("connection refused", "Environment Issue"),
    ("dns", "Environment Issue"),
    ("database unavailable", "Environment Issue"),
    ("assertionerror", "Test Issue"),
    ("expected", "Test Issue"),
    ("locator", "Test Issue"),
    ("element not found", "Test Issue"),
    ("stale element", "Test Issue"),
    ("nullpointerexception", "Product Bug"),
    ("500", "Product Bug"),
    ("internal server error", "Product Bug"),
    ("segmentation fault", "Product Bug"),
]


def infer_category_from_rules(log_text: str) -> str | None:
    """Infer a category using deterministic keyword rules."""
    lowered = log_text.lower()
    for token, category in _RULES:
        if token in lowered:
            return category
    return None


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


def apply_rule_override(result: dict[str, Any], log_text: str) -> dict[str, Any]:
    """Use deterministic rules to override/strengthen category prediction when possible."""
    rule_category = infer_category_from_rules(log_text)
    if not rule_category:
        return result

    normalized_category = _normalize_category(str(result.get("category") or ""))
    if normalized_category == rule_category:
        result["confidence"] = max(_normalize_confidence(result.get("confidence")), 0.75)
        return result

    result["category"] = rule_category
    result["confidence"] = max(_normalize_confidence(result.get("confidence")), 0.7)
    result["suggestion"] = result.get("suggestion") or "Validate logs around the failing step and rerun."
    return result


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
