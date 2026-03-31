"""Utility helpers for QA failure log preprocessing."""

from __future__ import annotations

import re
from typing import Iterable

_TIMESTAMP_PATTERNS: Iterable[re.Pattern[str]] = (
    re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d+)?\s*"),
    re.compile(r"^\[?\d{2}:\d{2}:\d{2}\]?\s*"),
)

_NOISE_PATTERNS: Iterable[re.Pattern[str]] = (
    re.compile(r"^(DEBUG|TRACE)\b", re.IGNORECASE),
    re.compile(r"^\s*$"),
)


def clean_log_text(log_text: str) -> str:
    """Remove noisy lines and common timestamp prefixes from logs."""
    if not log_text:
        return ""

    cleaned_lines: list[str] = []
    for raw_line in log_text.splitlines():
        line = raw_line.strip("\n")

        for timestamp_pattern in _TIMESTAMP_PATTERNS:
            line = timestamp_pattern.sub("", line)

        if any(pattern.search(line) for pattern in _NOISE_PATTERNS):
            continue

        cleaned_lines.append(line.rstrip())

    return "\n".join(cleaned_lines).strip()


def truncate_log(log_text: str, max_chars: int = 8000) -> str:
    """Truncate log content to the configured size while keeping useful tail context."""
    if len(log_text) <= max_chars:
        return log_text

    head_size = max_chars // 2
    tail_size = max_chars - head_size
    return (
        f"{log_text[:head_size]}\n\n"
        "...[TRUNCATED FOR ANALYSIS]...\n\n"
        f"{log_text[-tail_size:]}"
    )
