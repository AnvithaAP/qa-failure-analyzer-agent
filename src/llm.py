"""LLM analyzer role for QA failure analysis."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
logger = logging.getLogger("qa_failure_analyzer")

DEFAULT_PROMPT_VERSION = "v1"
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"

STRONG_PROMPT_SUFFIX = (
    "\n\nYou are in retry mode. Be conservative and choose a single most likely category. "
    "Avoid overfitting to generic keywords and favor concrete failure evidence."
)

SUMMARY_PROMPT = (
    "Summarize the QA failure log in <= 8 bullet points preserving stacktrace signals, "
    "exception names, environment hints, and probable failing component."
)


class Analyzer:
    """Analyzer role: owns all LLM interactions and prompt versioning."""

    def __init__(self, prompt_version: str = DEFAULT_PROMPT_VERSION, debug: bool = False) -> None:
        self.prompt_version = prompt_version
        self.debug = debug
        self.system_prompt = self._load_prompt(prompt_version)

    def _load_prompt(self, prompt_version: str) -> str:
        prompt_file = PROMPTS_DIR / f"{prompt_version}.txt"
        if not prompt_file.exists():
            raise ValueError(
                f"Unknown prompt version '{prompt_version}'. Expected file at {prompt_file}."
            )
        return prompt_file.read_text(encoding="utf-8").strip()

    @staticmethod
    def _build_user_prompt(log_text: str) -> str:
        return (
            f"Analyze this log and return strict JSON only:\n\n{log_text}\n\n"
            "JSON schema:\n"
            "{\n"
            '  "root_cause": "string",\n'
            '  "category": "Product Bug | Test Issue | Environment Issue",\n'
            '  "confidence": 0.0,\n'
            '  "confidence_reason": "string",\n'
            '  "suggestion": "string"\n'
            "}"
        )

    @staticmethod
    def _client() -> OpenAI:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is not set. Please configure your .env file.")
        return OpenAI(api_key=api_key)

    @staticmethod
    def _extract_usage(completion: Any, text: str) -> dict[str, float]:
        usage = getattr(completion, "usage", None)
        if usage:
            prompt_tokens = int(getattr(usage, "prompt_tokens", 0) or 0)
            completion_tokens = int(getattr(usage, "completion_tokens", 0) or 0)
            return {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens,
            }

        approx_total = max(1, int(len(text) / 4))
        return {
            "prompt_tokens": int(approx_total * 0.75),
            "completion_tokens": int(approx_total * 0.25),
            "total_tokens": approx_total,
        }

    def summarize_log(self, log_text: str) -> str:
        """Create a compact summary for very large logs before analysis."""
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        completion = self._client().chat.completions.create(
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

    def analyze_log(
        self,
        log_text: str,
        retries: int = 1,
        stronger_prompt: bool = False,
    ) -> tuple[dict[str, Any], str, dict[str, float]]:
        """Call LLM and parse strict JSON with retries. Returns parsed + raw response + usage."""
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        system_prompt = self.system_prompt + (STRONG_PROMPT_SUFFIX if stronger_prompt else "")

        last_error: Exception | None = None
        for attempt in range(retries + 1):
            try:
                logger.info("[INFO] Analyzer using prompt=%s model=%s", self.prompt_version, model)
                completion = self._client().chat.completions.create(
                    model=model,
                    temperature=0,
                    response_format={"type": "json_object"},
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": self._build_user_prompt(log_text)},
                    ],
                )

                raw_content = completion.choices[0].message.content
                if not raw_content:
                    raise RuntimeError("LLM returned empty response.")

                parsed = json.loads(raw_content)
                if not isinstance(parsed, dict):
                    raise RuntimeError("LLM response must be a JSON object.")

                usage = self._extract_usage(completion, raw_content)
                if self.debug:
                    logger.info("[DEBUG] Raw LLM response: %s", raw_content)
                    logger.info("[DEBUG] Parsed JSON: %s", json.dumps(parsed, indent=2))
                    logger.info("[DEBUG] Token usage: %s", usage)
                return parsed, raw_content, usage
            except (json.JSONDecodeError, RuntimeError, Exception) as exc:  # noqa: BLE001
                last_error = exc
                if attempt < retries:
                    logger.warning("LLM attempt %s failed, retrying once: %s", attempt + 1, exc)
                    continue
                raise RuntimeError(f"LLM analysis failed after retry: {exc}") from exc

        raise RuntimeError(f"LLM analysis failed unexpectedly: {last_error}")
