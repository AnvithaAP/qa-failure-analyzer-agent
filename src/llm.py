"""LLM integration for QA failure analysis."""

from __future__ import annotations

import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
logger = logging.getLogger("qa_failure_analyzer")

SYSTEM_PROMPT = (
    "You are a senior QA failure triage agent. "
    "Return only strict JSON with keys root_cause, category, confidence, suggestion. "
    "category must be one of: Product Bug, Test Issue, Environment Issue. "
    "confidence must be a float in range [0,1]."
)

STRONG_SYSTEM_PROMPT = (
    "You are a strict QA incident commander. "
    "Choose the single most likely category with conservative confidence. "
    "Return only strict JSON with root_cause, category, confidence, suggestion. "
    "category must be one of: Product Bug, Test Issue, Environment Issue. "
    "confidence must be a float in [0,1]."
)


SUMMARY_PROMPT = (
    "Summarize the QA failure log in <= 8 bullet points preserving stacktrace signals, "
    "exception names, environment hints, and probable failing component."
)


def _build_user_prompt(log_text: str) -> str:
    return (
        f"Analyze this log and return strict JSON only:\n\n{log_text}\n\n"
        "JSON schema:\n"
        "{\n"
        '  "root_cause": "string",\n'
        '  "category": "Product Bug | Test Issue | Environment Issue",\n'
        '  "confidence": 0.0,\n'
        '  "suggestion": "string"\n'
        "}"
    )


def _client() -> OpenAI:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Please configure your .env file.")
    return OpenAI(api_key=api_key)


def summarize_log(log_text: str) -> str:
    """Create a compact summary for very large logs before analysis."""
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = _client()

    completion = client.chat.completions.create(
        model=model,
        temperature=0,
        messages=[
            {"role": "system", "content": SUMMARY_PROMPT},
            {"role": "user", "content": log_text},
        ],
    )
    summary = completion.choices[0].message.content
    if not summary:
        raise RuntimeError("LLM returned empty summary.")
    return summary


def analyze_log(log_text: str, retries: int = 1, stronger_prompt: bool = False) -> dict[str, Any]:
    """Call the LLM and safely parse strict JSON with retries on failure."""
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = _client()
    system_prompt = STRONG_SYSTEM_PROMPT if stronger_prompt else SYSTEM_PROMPT

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            logger.info("[INFO] Sending to LLM")
            completion = client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": _build_user_prompt(log_text)},
                ],
            )

            raw_content = completion.choices[0].message.content
            if not raw_content:
                raise RuntimeError("LLM returned empty response.")

            logger.info("[INFO] Parsing response")
            parsed = json.loads(raw_content)
            if not isinstance(parsed, dict):
                raise RuntimeError("LLM response must be a JSON object.")
            return parsed
        except (json.JSONDecodeError, RuntimeError, Exception) as exc:  # noqa: BLE001
            last_error = exc
            if attempt < retries:
                logger.warning("LLM attempt %s failed, retrying once: %s", attempt + 1, exc)
                continue
            raise RuntimeError(f"LLM analysis failed after retry: {exc}") from exc

    raise RuntimeError(f"LLM analysis failed unexpectedly: {last_error}")
