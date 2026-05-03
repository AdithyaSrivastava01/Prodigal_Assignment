from __future__ import annotations

import random
import time
from abc import ABC, abstractmethod
from typing import Any

import anthropic

from payment_agent.config import (
    ANTHROPIC_API_KEY,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_RETRY_BASE_DELAY,
    LLM_RETRY_MAX_ATTEMPTS,
    LLM_TEMPERATURE,
)
from payment_agent.models import LLMResponse, ToolCall


class LLMClientBase(ABC):
    """Abstract interface for LLM calls. Enables DI for testing."""

    @abstractmethod
    def chat(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        """Send a chat request and return parsed response."""
        ...


class ClaudeLLMClient(LLMClientBase):
    """Real Claude API client using the anthropic SDK."""

    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        key = api_key or ANTHROPIC_API_KEY
        if not key:
            raise ValueError(
                "ANTHROPIC_API_KEY environment variable is required. "
                "Set it or pass api_key to ClaudeLLMClient."
            )
        self._client = anthropic.Anthropic(api_key=key)
        self._model = model or LLM_MODEL

    def chat(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": LLM_MAX_TOKENS,
            "temperature": LLM_TEMPERATURE,
            "system": system,
            "messages": messages,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = {"type": "any"}

        for attempt in range(LLM_RETRY_MAX_ATTEMPTS):
            try:
                response = self._client.messages.create(**kwargs)
                return self._parse_response(response)
            except (
                anthropic.RateLimitError,
                anthropic.InternalServerError,
                anthropic.APIConnectionError,
            ):
                if attempt < LLM_RETRY_MAX_ATTEMPTS - 1:
                    delay = LLM_RETRY_BASE_DELAY * (2**attempt)
                    jitter = random.uniform(0, delay * 0.1)
                    time.sleep(delay + jitter)
                    continue
                raise

        raise RuntimeError("LLM call failed after all retries")

    @staticmethod
    def _parse_response(response: anthropic.types.Message) -> LLMResponse:
        text_parts: list[str] = []
        tool_calls: list[ToolCall] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, input=block.input)
                )

        return LLMResponse(
            text=" ".join(text_parts) if text_parts else "",
            tool_calls=tool_calls,
            stop_reason=response.stop_reason or "",
        )


class MockLLMClient(LLMClientBase):
    """Deterministic mock for unit tests. Returns pre-configured responses."""

    def __init__(self, responses: list[LLMResponse] | None = None) -> None:
        self._responses = list(responses) if responses else []
        self._call_idx = 0
        self.calls: list[dict[str, Any]] = []

    def add_response(self, response: LLMResponse) -> None:
        self._responses.append(response)

    def chat(
        self,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> LLMResponse:
        self.calls.append(
            {
                "system": system,
                "messages": messages,
                "tools": tools,
            }
        )
        if self._call_idx < len(self._responses):
            resp = self._responses[self._call_idx]
            self._call_idx += 1
            return resp
        # Default: return empty text response
        return LLMResponse(text="", tool_calls=[], stop_reason="end_turn")
