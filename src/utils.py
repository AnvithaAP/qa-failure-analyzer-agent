"""Utility helpers for QA failure log preprocessing."""

from __future__ import annotations

import re
from typing import Any

MAX_LOG_CHARS = 1000

_TIMESTAMP_PATTERNS = (
    re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d+)?\s*"),
    re.compile(r"^\[?\d{2}:\d{2}:\d{2}\]?\s*"),
)

_NOISE_PATTERNS = (
    re.compile(r"^(DEBUG|TRACE)\b", re.IGNORECASE),
    re.compile(r"^\s*$"),
)

_ERROR_SIGNAL = re.compile(r"(error|exception|failed|timeout|assert)", re.IGNORECASE)


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


def detect_error_events(log_text: str) -> list[str]:
    """Return likely error events including continuation lines from stack traces."""
    events: list[str] = []
    current: list[str] = []

    for line in log_text.splitlines():
        is_signal = bool(_ERROR_SIGNAL.search(line))
        is_continuation = line.startswith((" ", "\t", "at ", "Caused by:"))

        if is_signal:
            if current:
                events.append("\n".join(current).strip())
            current = [line]
            continue

        if current and is_continuation:
            current.append(line)
        elif current:
            events.append("\n".join(current).strip())
            current = []

    if current:
        events.append("\n".join(current).strip())

    return [event for event in events if event]


def assess_log_quality(log_text: str) -> dict[str, Any]:
    """Detect real-world log issues such as truncation and sparse context."""
    lowered = log_text.lower()
    return {
        "is_truncated": "truncated" in lowered or "...[truncated" in lowered,
        "is_partial": len(log_text.splitlines()) < 3,
        "multi_error": len(detect_error_events(log_text)) > 1,
    }


def split_ci_log_stream(payload: str) -> list[str]:
    """Split a CI log stream into independent failure blocks."""
    blocks = re.split(r"\n\s*(?:={3,}|-{3,}|#{3,})\s*\n", payload)
    normalized = [block.strip() for block in blocks if block.strip()]
    if len(normalized) > 1:
        return normalized

    # Fallback: split by blank-line paragraphs when separators are absent.
    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", payload) if part.strip()]
    return paragraphs if len(paragraphs) > 1 else normalized


# Backwards-compatible alias.
clean_log_text = clean_log
