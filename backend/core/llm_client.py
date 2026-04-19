from __future__ import annotations

import json
import logging
import re

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


def _extract_json(raw: str) -> dict:
    """Extract JSON object from LLM output that may contain thinking blocks or fences."""
    # Strip <think>...</think> blocks
    text = re.sub(r"<think>.*?</think>", "", raw, flags=re.DOTALL)
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\s*\n?", "", text)

    # Find the first '{' and its matching '}' using brace-depth counter
    start = text.find("{")
    if start == -1:
        raise ValueError(
            f"No JSON object found in LLM response: {raw[:200]}"
        )

    depth = 0
    in_string = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == "\\":
            if in_string:
                escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start : i + 1])

    raise ValueError(
        f"No complete JSON object found in LLM response: {raw[:200]}"
    )


class LLMClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        enable_thinking: bool = False,
        thinking_budget: int = 32768,
    ):
        self.model = model
        self.enable_thinking = enable_thinking
        self.thinking_budget = thinking_budget
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    async def chat(self, messages: list[dict], **kwargs) -> str:
        if self.enable_thinking:
            extra = kwargs.pop("extra_body", {})
            extra.setdefault("enable_thinking", True)
            extra.setdefault("thinking_budget", self.thinking_budget)
            kwargs["extra_body"] = extra
        response = await self._client.chat.completions.create(
            model=self.model, messages=messages, **kwargs
        )
        return response.choices[0].message.content

    async def chat_json(
        self,
        messages: list[dict],
        response_schema: dict | None = None,
        max_retries: int = 2,
        **kwargs,
    ) -> dict:
        kwargs.setdefault("response_format", {"type": "json_object"})
        for attempt in range(max_retries):
            raw = await self.chat(messages, **kwargs)
            try:
                return _extract_json(raw)
            except (ValueError, json.JSONDecodeError) as e:
                if attempt + 1 >= max_retries:
                    raise ValueError(
                        f"Failed to parse LLM response as JSON "
                        f"after {max_retries} attempts: {e}"
                    ) from e
                logger.warning(
                    "JSON parse failed (attempt %d/%d): %s",
                    attempt + 1,
                    max_retries,
                    e,
                )
        # Unreachable, but satisfies type checkers
        raise RuntimeError("Unreachable")  # pragma: no cover
