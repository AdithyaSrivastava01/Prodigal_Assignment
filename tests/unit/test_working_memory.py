from __future__ import annotations

import pytest

from payment_agent.memory.working import EntityBuffer, WorkingMemory
from payment_agent.models import ConversationState


class TestEntityBuffer:
    def test_fill_name(self):
        buf = EntityBuffer()
        buf.fill({"full_name": "Nithin Jain"})
        assert buf.name == "Nithin Jain"

    def test_fill_ignores_none(self):
        buf = EntityBuffer()
        buf.fill({"full_name": None, "account_id": None})
        assert buf.name is None
        assert buf.account_id is None

    def test_fill_secondary_factors(self):
        buf = EntityBuffer()
        buf.fill({"dob": "1990-05-14", "pincode": "400001"})
        assert buf.secondary_factors == {"dob": "1990-05-14", "pincode": "400001"}

    def test_fill_card_fragments(self):
        buf = EntityBuffer()
        buf.fill({"card_number": "4532015112830366", "cvv": "123"})
        assert buf.card_fragments == {"card_number": "4532015112830366", "cvv": "123"}

    def test_fill_payment_intent(self):
        buf = EntityBuffer()
        buf.fill({"payment_intent": "full"})
        assert buf.payment_intent == "full"

    def test_fill_payment_amount(self):
        buf = EntityBuffer()
        buf.fill({"payment_amount": 500.0})
        assert buf.payment_amount == 500.0

    def test_drain_account_id(self):
        buf = EntityBuffer()
        buf.fill({"account_id": "ACC1001"})
        result = buf.drain_for_state(ConversationState.AWAITING_ACCOUNT_ID)
        assert result == {"account_id": "ACC1001"}
        assert buf.account_id is None

    def test_drain_name(self):
        buf = EntityBuffer()
        buf.fill({"full_name": "Nithin Jain"})
        result = buf.drain_for_state(ConversationState.AWAITING_NAME)
        assert result == {"name": "Nithin Jain"}
        assert buf.name is None

    def test_drain_secondary(self):
        buf = EntityBuffer()
        buf.fill({"dob": "1990-05-14"})
        result = buf.drain_for_state(ConversationState.AWAITING_SECONDARY)
        assert result == {"factors": {"dob": "1990-05-14"}}
        assert buf.secondary_factors == {}

    def test_drain_amount(self):
        buf = EntityBuffer()
        buf.fill({"payment_amount": 500.0})
        result = buf.drain_for_state(ConversationState.BALANCE_DISCLOSED)
        assert result == {"amount": 500.0}

    def test_drain_payment_intent_full(self):
        buf = EntityBuffer()
        buf.fill({"payment_intent": "full"})
        result = buf.drain_for_state(ConversationState.BALANCE_DISCLOSED)
        assert result == {"payment_intent": "full"}

    def test_drain_card(self):
        buf = EntityBuffer()
        buf.fill({"card_number": "4532015112830366", "cvv": "123"})
        result = buf.drain_for_state(ConversationState.COLLECTING_CARD)
        assert result == {
            "card_fragments": {"card_number": "4532015112830366", "cvv": "123"}
        }
        assert buf.card_fragments == {}

    def test_drain_irrelevant_state_returns_empty(self):
        buf = EntityBuffer()
        buf.fill({"full_name": "Nithin Jain"})
        result = buf.drain_for_state(ConversationState.COLLECTING_CARD)
        assert result == {}
        assert buf.name == "Nithin Jain"

    def test_fill_multiple_then_drain_sequentially(self):
        buf = EntityBuffer()
        buf.fill(
            {
                "account_id": "ACC1001",
                "full_name": "Nithin Jain",
                "dob": "1990-05-14",
                "payment_intent": "full",
            }
        )
        r1 = buf.drain_for_state(ConversationState.AWAITING_ACCOUNT_ID)
        assert r1 == {"account_id": "ACC1001"}
        r2 = buf.drain_for_state(ConversationState.AWAITING_NAME)
        assert r2 == {"name": "Nithin Jain"}
        r3 = buf.drain_for_state(ConversationState.AWAITING_SECONDARY)
        assert r3 == {"factors": {"dob": "1990-05-14"}}


class TestWorkingMemory:
    def test_initial_state(self):
        wm = WorkingMemory()
        assert wm.state == ConversationState.GREETING
        assert wm.verified is False
        assert wm.verification_attempts == 0
        assert wm.account_id is None

    def test_entity_buffer_initialized(self):
        wm = WorkingMemory()
        assert isinstance(wm.entity_buffer, EntityBuffer)
