"""LLM integration for QA failure analysis."""

from __future__ import annotations

import json
import os
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

SYSTEM_PROMPT = (
    "You are a senior QA engineer analyzing test failures.\n"
    "Given logs, identify the root cause, classify the failure,\n"
    "and suggest actionable fixes."
)


def _build_user_prompt(log_text: str) -> str:
    return (
        f"LOG:\n{log_text}\n\n"
        "Return JSON:\n"
        "{\n"
        '"root_cause": "...",\n'
        '"category": "...",\n'
        '"confidence": 0.0,\n'
        '"suggestion": "..."\n'
        "}"
    )


def analyze_log(log_text: str) -> dict[str, Any]:
    """Send log content to LLM and parse structured JSON output."""
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set. Please configure your .env file.")

    client = OpenAI(api_key=api_key)
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
        raise RuntimeError("LLM returned an empty response.")

    try:
        parsed = json.loads(raw_content)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"LLM response was not valid JSON: {raw_content}") from exc

    if not isinstance(parsed, dict):
        raise RuntimeError("LLM response JSON must be an object.")

    return parsed
