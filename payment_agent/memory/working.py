from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, Field

from payment_agent.models import AccountData, CardDetails, ConversationState

_ACCOUNT_ID_RE = re.compile(r"^ACC\d+$")
_DOB_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_AADHAAR_LAST4_RE = re.compile(r"^\d{4}$")
_PINCODE_RE = re.compile(r"^\d{6}$")


class EntityBuffer(BaseModel):
    """Queues entities extracted from user input for flow-order processing.

    Entities may arrive out of order (e.g., user provides name + account ID
    in greeting). The buffer stores them and drain_for_state() returns only
    entities relevant to the current state, clearing them after consumption.
    """

    account_id: str | None = None
    name: str | None = None
    secondary_factors: dict[str, str] = Field(default_factory=dict)
    payment_amount: float | None = None
    payment_intent: str | None = None
    card_fragments: dict[str, Any] = Field(default_factory=dict)
    is_decline: bool = False
    is_affirmative: bool = False

    def fill(self, extracted: dict[str, Any]) -> None:
        """Merge extracted entities into buffer. None values are ignored.

        Applies format validation as a guardrail — rejects garbage values
        that the LLM may hallucinate when forced to call the extraction tool.
        """
        aid = extracted.get("account_id")
        if aid and _ACCOUNT_ID_RE.match(str(aid)):
            self.account_id = str(aid)
        if extracted.get("full_name"):
            name = str(extracted["full_name"]).strip()
            if len(name) >= 2:
                self.name = name
        if extracted.get("dob"):
            val = str(extracted["dob"])
            if _DOB_RE.match(val):
                self.secondary_factors["dob"] = val
        if extracted.get("aadhaar_last4"):
            val = str(extracted["aadhaar_last4"])
            if _AADHAAR_LAST4_RE.match(val):
                self.secondary_factors["aadhaar_last4"] = val
        if extracted.get("pincode"):
            val = str(extracted["pincode"])
            if _PINCODE_RE.match(val):
                self.secondary_factors["pincode"] = val
        if extracted.get("payment_amount") is not None:
            self.payment_amount = extracted["payment_amount"]
        if extracted.get("payment_intent"):
            self.payment_intent = extracted["payment_intent"]
        for key in (
            "card_number",
            "cvv",
            "cardholder_name",
            "expiry_month",
            "expiry_year",
        ):
            if extracted.get(key) is not None:
                self.card_fragments[key] = extracted[key]
        if extracted.get("is_decline"):
            self.is_decline = True
        if extracted.get("is_affirmative"):
            self.is_affirmative = True

    def drain_for_state(self, state: ConversationState) -> dict[str, Any]:
        """Return + clear entities relevant to given state."""
        result: dict[str, Any] = {}

        if state in (ConversationState.GREETING, ConversationState.AWAITING_ACCOUNT_ID):
            if self.account_id:
                result["account_id"] = self.account_id
                self.account_id = None

        elif state == ConversationState.AWAITING_NAME:
            if self.name:
                result["name"] = self.name
                self.name = None

        elif state == ConversationState.AWAITING_SECONDARY:
            if self.secondary_factors:
                result["factors"] = dict(self.secondary_factors)
                self.secondary_factors.clear()

        elif state in (
            ConversationState.BALANCE_DISCLOSED,
            ConversationState.AWAITING_AMOUNT,
        ):
            if self.payment_amount is not None:
                result["amount"] = self.payment_amount
                self.payment_amount = None
            elif self.payment_intent:
                result["payment_intent"] = self.payment_intent
                self.payment_intent = None

        elif state == ConversationState.COLLECTING_CARD:
            if self.card_fragments:
                result["card_fragments"] = dict(self.card_fragments)
                self.card_fragments.clear()

        return result

    def has_decline(self) -> bool:
        """Check and clear decline flag."""
        if self.is_decline:
            self.is_decline = False
            return True
        return False

    def has_affirmative(self) -> bool:
        """Check and clear affirmative flag."""
        if self.is_affirmative:
            self.is_affirmative = False
            return True
        return False


class WorkingMemory(BaseModel):
    """Tier 1: Structured state — source of truth for the state machine.

    The state machine reads ONLY this. Claude never modifies it directly.
    Extractions go through validation before updating fields here.
    """

    state: ConversationState = ConversationState.GREETING
    account_id: str | None = None
    account_data: AccountData | None = None
    verified: bool = False
    verification_attempts: int = 0
    payment_attempts: int = 0
    collected_name: str | None = None
    payment_amount: float | None = None
    card_details: CardDetails = Field(default_factory=CardDetails)
    transaction_id: str | None = None
    entity_buffer: EntityBuffer = Field(default_factory=EntityBuffer)
    turn_count: int = 0
