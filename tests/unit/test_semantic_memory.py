from __future__ import annotations

from payment_agent.memory.semantic import SemanticMemory


class TestSemanticMemory:
    def test_empty_context(self):
        mem = SemanticMemory()
        assert mem.build_context_block() == ""

    def test_record_single_fact(self):
        mem = SemanticMemory()
        mem.record("identity", "Account ACC1001 located", turn=1)
        block = mem.build_context_block()
        assert "[identity]" in block
        assert "ACC1001" in block

    def test_record_multiple_facts(self):
        mem = SemanticMemory()
        mem.record("identity", "Account ACC1001 located", turn=1)
        mem.record("verification", "Name verified", turn=2)
        mem.record("payment", "Balance: Rs.1,250.75", turn=3)
        block = mem.build_context_block()
        assert "[identity]" in block
        assert "[verification]" in block
        assert "[payment]" in block

    def test_facts_ordered_by_turn(self):
        mem = SemanticMemory()
        mem.record("payment", "Balance disclosed", turn=3)
        mem.record("identity", "Account found", turn=1)
        block = mem.build_context_block()
        lines = [line for line in block.strip().split("\n") if line.startswith("[")]
        assert "identity" in lines[0]
        assert "payment" in lines[1]

    def test_get_facts_returns_copy(self):
        mem = SemanticMemory()
        mem.record("test", "fact", turn=1)
        facts = mem.get_facts()
        assert len(facts) == 1
        facts.clear()
        assert len(mem.get_facts()) == 1  # original unmodified
