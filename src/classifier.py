"""Rule-based classifier role and output validation."""

from __future__ import annotations

import json
import logging
from typing import Any

ALLOWED_CATEGORIES = {"Product Bug", "Test Issue", "Environment Issue"}
logger = logging.getLogger("qa_failure_analyzer")

_RULES: list[tuple[str, str]] = [
    ("timeout", "Environment Issue"),
    ("timed out", "Environment Issue"),
    ("connection refused", "Environment Issue"),
    ("database unavailable", "Environment Issue"),
    ("assertionerror", "Test Issue"),
    ("nosuchelementexception", "Test Issue"),
    ("locator", "Test Issue"),
    ("element not found", "Test Issue"),
    ("http 500", "Product Bug"),
    ("internal server error", "Product Bug"),
    ("nullpointerexception", "Product Bug"),
]


def _normalize_confidence(confidence: Any) -> float:
    try:
        parsed = float(confidence)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, parsed))


def _normalize_latency(latency: Any) -> float:
    try:
        parsed = float(latency)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, parsed)


def _ensure_shape(result: dict[str, Any]) -> dict[str, Any]:
    return {
        "root_cause": str(result.get("root_cause") or "Unable to determine from provided log.").strip(),
        "category": str(result.get("category") or "Test Issue").strip(),
        "confidence": _normalize_confidence(result.get("confidence")),
        "suggestion": str(result.get("suggestion") or "Collect additional logs and retry analysis.").strip(),
        "latency": _normalize_latency(result.get("latency", 0.0)),
    }


def infer_category_from_rules(log_text: str) -> str | None:
    lowered = log_text.lower()
    for token, category in _RULES:
        if token in lowered:
            return category
    return None


class Classifier:
    """Classifier role: merges LLM output with deterministic rules."""

    def __init__(self, debug: bool = False) -> None:
        self.debug = debug

    def classify_failure(self, result: dict[str, Any], log_text: str) -> tuple[dict[str, Any], str | None]:
        output = _ensure_shape(result)
        rule_category = infer_category_from_rules(log_text)
        if not rule_category:
            if self.debug:
                logger.info("[DEBUG] Classification adjustments: none (no rule match)")
            return output, None

        adjustment_reason: str | None = None
        if output["category"] != rule_category:
            adjustment_reason = (
                f"Rule override applied: '{output['category']}' -> '{rule_category}' based on keyword evidence"
            )
            output["category"] = rule_category
            output["confidence"] = max(output["confidence"], 0.75)
        if self.debug:
            logger.info("[DEBUG] Classification adjustments: %s", adjustment_reason or "none")
            logger.info("[DEBUG] Classified output: %s", json.dumps(output, indent=2))
        return output, adjustment_reason


def classify_failure(result: dict[str, Any], log_text: str) -> dict[str, Any]:
    """Backward-compatible helper function."""
    classified, _ = Classifier(debug=False).classify_failure(result, log_text)
    return classified


def validate_output(result: dict[str, Any]) -> dict[str, Any]:
    """Validate final output shape and business constraints."""
    output = _ensure_shape(result)
    if output["category"] not in ALLOWED_CATEGORIES:
        raise ValueError(f"Invalid category: {output['category']}")

    if not 0.0 <= output["confidence"] <= 1.0:
        raise ValueError(f"Invalid confidence: {output['confidence']}")

    if output["latency"] < 0.0:
        raise ValueError(f"Invalid latency: {output['latency']}")

    return output
