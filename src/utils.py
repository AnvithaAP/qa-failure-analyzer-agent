"""Utility helpers for QA failure log preprocessing."""

from __future__ import annotations

import re

MAX_LOG_CHARS = 1000

_TIMESTAMP_PATTERNS = (
    re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d+)?\s*"),
    re.compile(r"^\[?\d{2}:\d{2}:\d{2}\]?\s*"),
)

_NOISE_PATTERNS = (
    re.compile(r"^(DEBUG|TRACE)\b", re.IGNORECASE),
    re.compile(r"^\s*$"),
)


def clean_log(log: str) -> str:
    """Clean log lines by removing timestamps/noise and truncating long payloads."""
    if not log:
        return ""

    cleaned_lines: list[str] = []
    for raw_line in log.splitlines():
        line = raw_line.strip("\n")
        for timestamp_pattern in _TIMESTAMP_PATTERNS:
            line = timestamp_pattern.sub("", line)

        if any(pattern.search(line) for pattern in _NOISE_PATTERNS):
            continue

        cleaned_lines.append(line.rstrip())

    return truncate_log("\n".join(cleaned_lines).strip(), max_chars=MAX_LOG_CHARS)


def truncate_log(log: str, max_chars: int = MAX_LOG_CHARS) -> str:
    """Truncate large logs while preserving beginning and tail context."""
    if len(log) <= max_chars:
        return log

    head_size = max_chars // 2
    tail_size = max_chars - head_size
    return (
        f"{log[:head_size]}\n\n"
        "...[TRUNCATED FOR ANALYSIS]...\n\n"
        f"{log[-tail_size:]}"
    )


# Backwards-compatible alias.
clean_log_text = clean_log
