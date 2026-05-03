from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Fact:
    """A single established fact from the conversation."""

    category: str
    content: str
    turn: int


class SemanticMemory:
    """Tier 3: Extracted facts injected into Claude's system prompt.

    Append-only fact store (following mem0's ADD-only pattern).
    Facts contain NO PII — only states and outcomes.
    """

    def __init__(self) -> None:
        self._facts: list[Fact] = []

    def record(self, category: str, content: str, turn: int) -> None:
        """Record a verified fact from the conversation."""
        self._facts.append(Fact(category=category, content=content, turn=turn))

    def build_context_block(self) -> str:
        """Format facts as a context block for system prompt injection."""
        if not self._facts:
            return ""
        sorted_facts = sorted(self._facts, key=lambda f: f.turn)
        lines = [f"[{f.category}] {f.content}" for f in sorted_facts]
        return "=== Known Context ===\n" + "\n".join(lines)

    def get_facts(self) -> list[Fact]:
        """Return a copy of all facts."""
        return list(self._facts)
