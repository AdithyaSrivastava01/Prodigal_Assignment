from __future__ import annotations

from copy import deepcopy
from typing import Any


class ConversationMemory:
    """Tier 2: Conversation history with sliding window.

    Stores full message history for the conversation. When history exceeds
    the window size, older messages are stored separately. get_messages_for_claude()
    returns a summary prefix (if overflow exists) plus the last N messages.
    """

    def __init__(self, window_size: int = 20) -> None:
        self._messages: list[dict[str, Any]] = []
        self._window_size = window_size
        self._overflow: list[dict[str, Any]] = []
        self._summary: str | None = None

    def add_user_message(self, content: str) -> None:
        self._messages.append({"role": "user", "content": content})
        self._check_overflow()

    def redact_last_user_message(self, redacted: str) -> None:
        """Replace the content of the most recent user message (post-extraction redaction)."""
        for msg in reversed(self._messages):
            if msg["role"] == "user" and isinstance(msg["content"], str):
                msg["content"] = redacted
                break

    def add_assistant_message(self, content: str) -> None:
        self._messages.append({"role": "assistant", "content": content})
        self._check_overflow()

    def add_assistant_tool_use(
        self, tool_use_id: str, tool_name: str, tool_input: dict
    ) -> None:
        """Add an assistant message containing a tool_use block."""
        self._messages.append(
            {
                "role": "assistant",
                "content": [
                    {
                        "type": "tool_use",
                        "id": tool_use_id,
                        "name": tool_name,
                        "input": tool_input,
                    }
                ],
            }
        )
        self._check_overflow()

    def add_tool_result(self, tool_use_id: str, sanitized_result: str) -> None:
        """Add a tool result. Content is pre-sanitized — no raw PII."""
        self._messages.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_use_id,
                        "content": sanitized_result,
                    }
                ],
            }
        )
        self._check_overflow()

    def get_messages_for_claude(self) -> list[dict[str, Any]]:
        """Return messages for Claude API: [summary] + recent window."""
        if not self._messages:
            return []

        result: list[dict[str, Any]] = []

        if self._summary:
            result.append(
                {
                    "role": "user",
                    "content": f"[Previous conversation summary: {self._summary}]",
                }
            )
            # Need an assistant ack to maintain valid alternation
            result.append(
                {
                    "role": "assistant",
                    "content": "Understood, I have the context from our previous conversation.",
                }
            )

        # Return all messages if within window, otherwise last N
        if len(self._messages) <= self._window_size:
            result.extend(deepcopy(self._messages))
        else:
            result.extend(deepcopy(self._messages[-self._window_size :]))

        return result

    def get_full_history(self) -> list[dict[str, Any]]:
        """Return complete conversation history (for logging/eval)."""
        return deepcopy(self._overflow + self._messages)

    def set_summary(self, summary: str) -> None:
        """Set the overflow summary (generated externally by LLM)."""
        self._summary = summary

    def _check_overflow(self) -> None:
        """Move oldest messages to overflow when window exceeded."""
        if len(self._messages) > self._window_size * 2:
            overflow_count = len(self._messages) - self._window_size
            self._overflow.extend(self._messages[:overflow_count])
            self._messages = self._messages[overflow_count:]
