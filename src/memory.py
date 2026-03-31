"""Lightweight JSON memory for previous analyses."""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

MEMORY_PATH = Path("memory.json")
_DEFAULT_MAX_ITEMS = 500
_DEFAULT_SIMILARITY_THRESHOLD = 0.85
_SIGNATURE_SIMILARITY_THRESHOLD = 0.7


_ERROR_PATTERNS = [
    re.compile(r"\b\w*error\b", re.IGNORECASE),
    re.compile(r"\b\w*exception\b", re.IGNORECASE),
    re.compile(r"http\s+\d{3}", re.IGNORECASE),
]


def _load_memory(path: Path = MEMORY_PATH) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []

    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    return []


def _extract_error_signature(log: str) -> str:
    lines = [line.strip() for line in log.splitlines() if line.strip()]
    matches: list[str] = []
    for line in lines:
        if any(pattern.search(line) for pattern in _ERROR_PATTERNS):
            matches.append(line.lower())
    signature = " | ".join(matches[:5])
    return signature[:500]


def store_result(log: str, result: dict[str, Any], path: Path = MEMORY_PATH, max_items: int = _DEFAULT_MAX_ITEMS) -> None:
    """Persist analyzed logs and results for future similarity checks."""
    entries = _load_memory(path)
    entries.append({"log": log, "signature": _extract_error_signature(log), "result": result})
    if len(entries) > max_items:
        entries = entries[-max_items:]
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def retrieve_similar(
    log: str,
    path: Path = MEMORY_PATH,
    threshold: float = _DEFAULT_SIMILARITY_THRESHOLD,
) -> dict[str, Any] | None:
    """Return the most similar previous analysis if above similarity threshold and signature is compatible."""
    best_score = 0.0
    best_result: dict[str, Any] | None = None

    target_signature = _extract_error_signature(log)

    for entry in _load_memory(path):
        prior_log = str(entry.get("log", ""))
        prior_signature = str(entry.get("signature") or _extract_error_signature(prior_log))
        if target_signature and prior_signature:
            signature_score = SequenceMatcher(None, target_signature, prior_signature).ratio()
            if signature_score < _SIGNATURE_SIMILARITY_THRESHOLD:
                continue

        score = SequenceMatcher(None, log, prior_log).ratio()
        if score > best_score and score >= threshold:
            result = entry.get("result")
            if isinstance(result, dict):
                best_score = score
                best_result = dict(result)

    return best_result
