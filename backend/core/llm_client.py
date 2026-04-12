from __future__ import annotations
import json
from openai import AsyncOpenAI

class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self.model = model
        self._client = AsyncOpenAI(base_url=base_url, api_key=api_key)

    async def chat(self, messages: list[dict], **kwargs) -> str:
        response = await self._client.chat.completions.create(model=self.model, messages=messages, **kwargs)
        return response.choices[0].message.content

    async def chat_json(self, messages: list[dict], response_schema: dict, **kwargs) -> dict:
        kwargs.setdefault("response_format", {"type": "json_object"})
        raw = await self.chat(messages, **kwargs)
        try:
            return json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to parse LLM response as JSON: {e}") from e
