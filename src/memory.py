"""Lightweight JSON memory for previous analyses."""

from __future__ import annotations

import json
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

MEMORY_PATH = Path("memory.json")
_DEFAULT_MAX_ITEMS = 500


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


def store_result(log: str, result: dict[str, Any], path: Path = MEMORY_PATH, max_items: int = _DEFAULT_MAX_ITEMS) -> None:
    """Persist analyzed logs and results for future similarity checks."""
    entries = _load_memory(path)
    entries.append({"log": log, "result": result})
    if len(entries) > max_items:
        entries = entries[-max_items:]
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")


def retrieve_similar(log: str, path: Path = MEMORY_PATH, threshold: float = 0.9) -> dict[str, Any] | None:
    """Return the most similar previous analysis if above similarity threshold."""
    best_score = 0.0
    best_result: dict[str, Any] | None = None

    for entry in _load_memory(path):
        prior_log = str(entry.get("log", ""))
        score = SequenceMatcher(None, log, prior_log).ratio()
        if score > best_score and score >= threshold:
            result = entry.get("result")
            if isinstance(result, dict):
                best_score = score
                best_result = dict(result)

    return best_result
