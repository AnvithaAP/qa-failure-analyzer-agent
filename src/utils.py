"""Utility helpers for QA failure log preprocessing."""

from __future__ import annotations

import re
from typing import Any

MAX_LOG_CHARS = 20000
MAX_INPUT_CHARS = 50000

_TIMESTAMP_PATTERNS = (
    re.compile(r"^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:,\d+)?\s*"),
    re.compile(r"^\[?\d{2}:\d{2}:\d{2}\]?\s*"),
)

_NOISE_PATTERNS = (
    re.compile(r"^(DEBUG|TRACE)\b", re.IGNORECASE),
    re.compile(r"^\s*$"),
)

_ERROR_SIGNAL = re.compile(r"(error|exception|failed|timeout|assert)", re.IGNORECASE)
_INJECTION_PATTERNS = (
    re.compile(r"ignore\s+previous\s+instructions", re.IGNORECASE),
    re.compile(r"system\s*:\s*", re.IGNORECASE),
    re.compile(r"assistant\s*:\s*", re.IGNORECASE),
    re.compile(r"developer\s*:\s*", re.IGNORECASE),
    re.compile(r"\<\/?(system|assistant|developer|tool)\>", re.IGNORECASE),
)
_SUSPICIOUS_PATTERNS = (
    re.compile(r"rm\s+-rf\s+/", re.IGNORECASE),
    re.compile(r"curl\s+.+\|\s*sh", re.IGNORECASE),
    re.compile(r"powershell\s+-enc", re.IGNORECASE),
)
_SENSITIVE_PATTERNS = (
    re.compile(r"(?i)\b(authorization|api[_-]?key|secret|token|password)\s*[:=]\s*([^\r\n]+)"),
    re.compile(r"(?i)\bset-cookie\s*:\s*([^\r\n]+)"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
)
_SENSITIVE_MASK = "[REDACTED]"


def _redact_sensitive(line: str) -> tuple[str, int]:
    redacted = line
    replacements = 0
    for pattern in _SENSITIVE_PATTERNS:
        redacted, count = pattern.subn(_SENSITIVE_MASK, redacted)
        replacements += count
    return redacted, replacements


def sanitize_input(log: str, max_chars: int = MAX_INPUT_CHARS) -> tuple[str, dict[str, Any]]:
    """Sanitize raw input logs for prompt safety and bounded processing."""
    if not log:
        return "", {"was_truncated": False, "removed_injection": 0, "removed_suspicious": 0, "redacted_sensitive": 0}

    lines: list[str] = []
    removed_injection = 0
    removed_suspicious = 0
    redacted_sensitive = 0

    for raw_line in log.splitlines():
        line = raw_line.strip("\n")
        if any(pattern.search(line) for pattern in _INJECTION_PATTERNS):
            removed_injection += 1
            continue
        if any(pattern.search(line) for pattern in _SUSPICIOUS_PATTERNS):
            removed_suspicious += 1
            continue
        line, redactions = _redact_sensitive(line)
        redacted_sensitive += redactions
        lines.append(line)

    sanitized = "\n".join(lines).strip()
    was_truncated = len(sanitized) > max_chars
    if was_truncated:
        sanitized = sanitized[:max_chars]

    metadata = {
        "was_truncated": was_truncated,
        "removed_injection": removed_injection,
        "removed_suspicious": removed_suspicious,
        "redacted_sensitive": redacted_sensitive,
    }
    return sanitized, metadata


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
    events = detect_error_events(log_text)
    return {
        "is_truncated": "truncated" in lowered or "...[truncated" in lowered,
        "is_partial": len(log_text.splitlines()) < 3,
        "multi_error": len(events) > 1,
        "has_error_signal": bool(events),
    }


def split_ci_log_stream(payload: str) -> list[str]:
    """Split a CI log stream into independent failure blocks."""
    blocks = re.split(r"\n\s*(?:={3,}|-{3,}|#{3,})\s*\n", payload)
    normalized = [block.strip() for block in blocks if block.strip()]
    if len(normalized) > 1:
        return normalized

    paragraphs = [part.strip() for part in re.split(r"\n\s*\n", payload) if part.strip()]
    return paragraphs if len(paragraphs) > 1 else normalized


clean_log_text = clean_log
