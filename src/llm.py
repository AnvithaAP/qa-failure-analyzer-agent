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


def analyze_log(log_text: str, retries: int = 1) -> dict[str, Any]:
    """Call the LLM and safely parse strict JSON with one retry on failure."""
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    client = _client()

    last_error: Exception | None = None
    for attempt in range(retries + 1):
        try:
            logger.info("[INFO] Sending to LLM")
            completion = client.chat.completions.create(
                model=model,
                temperature=0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
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
