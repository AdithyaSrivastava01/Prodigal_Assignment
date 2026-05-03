from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Field


class ConversationState(str, Enum):
    """States in the payment collection conversation flow."""

    GREETING = "greeting"
    AWAITING_ACCOUNT_ID = "awaiting_account_id"
    AWAITING_NAME = "awaiting_name"
    AWAITING_SECONDARY = "awaiting_secondary"
    BALANCE_DISCLOSED = "balance_disclosed"
    AWAITING_AMOUNT = "awaiting_amount"
    COLLECTING_CARD = "collecting_card"
    PAYMENT_COMPLETE = "payment_complete"
    CLOSED = "closed"


class AccountData(BaseModel):
    """Account data returned by the lookup API."""

    account_id: str
    full_name: str
    dob: str
    aadhaar_last4: str
    pincode: str
    balance: float


class CardDetails(BaseModel):
    """Card payment details collected from the user."""

    cardholder_name: str | None = None
    card_number: str | None = None
    cvv: str | None = None
    expiry_month: int | None = None
    expiry_year: int | None = None

    def is_complete(self) -> bool:
        return all(
            [
                self.cardholder_name is not None,
                self.card_number is not None,
                self.cvv is not None,
                self.expiry_month is not None,
                self.expiry_year is not None,
            ]
        )

    def missing_fields(self) -> list[str]:
        missing: list[str] = []
        if not self.cardholder_name:
            missing.append("cardholder name")
        if not self.card_number:
            missing.append("card number")
        if not self.cvv:
            missing.append("CVV")
        if self.expiry_month is None or self.expiry_year is None:
            missing.append("expiry date (MM/YYYY)")
        return missing

    def to_api_dict(self) -> dict:
        return {
            "cardholder_name": self.cardholder_name,
            "card_number": self.card_number,
            "cvv": self.cvv,
            "expiry_month": self.expiry_month,
            "expiry_year": self.expiry_year,
        }


class ConversationContext(BaseModel):
    """Maintains full conversation state between turns."""

    state: ConversationState = ConversationState.GREETING
    account_id: str | None = None
    account_data: AccountData | None = None
    verified: bool = False
    verification_attempts: int = 0
    collected_name: str | None = None
    payment_amount: float | None = None
    card_details: CardDetails = Field(default_factory=CardDetails)
    transaction_id: str | None = None
    payment_attempts: int = 0


@dataclass
class ToolCall:
    """A tool call from Claude's response."""

    id: str
    name: str
    input: dict


@dataclass
class LLMResponse:
    """Parsed response from Claude API."""

    text: str
    tool_calls: list[ToolCall]
    stop_reason: str
