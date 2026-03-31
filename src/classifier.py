"""Rule-based classifier role and output validation."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger("qa_failure_analyzer")

_CATEGORIES_PATH = Path(__file__).resolve().parent / "categories.json"

_RULES: list[tuple[str, str, int]] = [
    ("database unavailable", "Environment Issue", 95),
    ("connection refused", "Environment Issue", 90),
    ("timeout", "Environment Issue", 80),
    ("timed out", "Environment Issue", 80),
    ("http 500", "Product Bug", 88),
    ("internal server error", "Product Bug", 88),
    ("nullpointerexception", "Product Bug", 85),
    ("assertionerror", "Test Issue", 82),
    ("nosuchelementexception", "Test Issue", 83),
    ("locator", "Test Issue", 75),
    ("element not found", "Test Issue", 78),
]


def _load_categories() -> set[str]:
    if not _CATEGORIES_PATH.exists():
        return {"Product Bug", "Test Issue", "Environment Issue"}
    payload = json.loads(_CATEGORIES_PATH.read_text(encoding="utf-8"))
    categories = payload.get("categories", [])
    return {str(item).strip() for item in categories if str(item).strip()}


ALLOWED_CATEGORIES = _load_categories()


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
        "confidence_reason": str(result.get("confidence_reason") or "Moderate confidence due to partial signal coverage.").strip(),
        "suggestion": str(result.get("suggestion") or "Collect additional logs and retry analysis.").strip(),
        "latency": _normalize_latency(result.get("latency", 0.0)),
    }


def infer_category_from_rules(log_text: str) -> str | None:
    outcome = infer_rule_signal(log_text)
    return outcome["category"] if outcome else None


def infer_rule_signal(log_text: str) -> dict[str, Any] | None:
    lowered = log_text.lower()
    best_match: tuple[str, str, int] | None = None
    for token, category, severity in _RULES:
        if token in lowered and (best_match is None or severity > best_match[2]):
            best_match = (token, category, severity)
    if not best_match:
        return None
    return {"token": best_match[0], "category": best_match[1], "severity": best_match[2]}


class Classifier:
    """Classifier role: merges LLM output with deterministic rules."""

    def __init__(self, debug: bool = False) -> None:
        self.debug = debug

    def classify_failure(self, result: dict[str, Any], log_text: str) -> tuple[dict[str, Any], str | None]:
        output = _ensure_shape(result)
        rule_signal = infer_rule_signal(log_text)
        if not rule_signal:
            if self.debug:
                logger.info("[DEBUG] Classification adjustments: none (no rule match)")
            return output, None

        adjustment_reason: str | None = None
        if output["category"] != rule_signal["category"]:
            adjustment_reason = (
                f"Rule override applied: '{output['category']}' -> '{rule_signal['category']}' "
                f"based on keyword '{rule_signal['token']}'"
            )
            output["category"] = rule_signal["category"]
            output["confidence"] = max(output["confidence"], min(0.98, rule_signal["severity"] / 100))

        output["confidence_reason"] = (
            f"Confidence combines keyword match, LLM certainty, and rule overrides; "
            f"strongest signal='{rule_signal['token']}' (severity={rule_signal['severity']})."
        )

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
