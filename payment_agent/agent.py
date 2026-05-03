from __future__ import annotations

import logging
import re
from typing import Any

from payment_agent.api_client import PaymentAPIClient, PaymentAPIClientBase
from payment_agent.config import MAX_PAYMENT_ATTEMPTS, MAX_VERIFICATION_ATTEMPTS
from payment_agent.llm.client import ClaudeLLMClient, LLMClientBase
from payment_agent.llm.prompts import get_system_prompt
from payment_agent.llm.safety import PIIScanner
from payment_agent.llm.tools import get_tools_for_state
from payment_agent.memory.conversation import ConversationMemory
from payment_agent.memory.semantic import SemanticMemory
from payment_agent.memory.working import WorkingMemory
from payment_agent.models import CardDetails, ConversationState, LLMResponse
from payment_agent.validators import (
    validate_amount,
    validate_card_number,
    validate_cvv,
    validate_date_format,
    validate_expiry,
)
from payment_agent.verification import VerificationService

logger = logging.getLogger(__name__)

MAX_INPUT_LENGTH = 500
MAX_TURNS = 30

_CARD_NUMBER_RE = re.compile(r"\b(\d{4})\d{8,11}(\d{4})\b")
_CVV_RE = re.compile(r"(?i)(cvv[:\s]*)(\d{3,4})")


def _redact_card_data(text: str) -> str:
    """Mask card numbers and CVVs before storing in conversation memory."""
    text = _CARD_NUMBER_RE.sub(r"\1********\2", text)
    text = _CVV_RE.sub(r"\1***", text)
    return text


def _fmt(amount: float) -> str:
    return f"\u20b9{amount:,.2f}"


PAYMENT_ERROR_MESSAGES: dict[str, str] = {
    "invalid_amount": "The payment amount is invalid.",
    "insufficient_balance": "The payment amount exceeds your outstanding balance.",
    "invalid_card": "The card number is invalid. Please check and try again.",
    "invalid_cvv": "The CVV provided is invalid.",
    "invalid_expiry": "The card expiry date is invalid or the card has expired.",
    "network_error": "Unable to connect to the payment server. Please try again.",
    "unknown_error": "An unexpected error occurred. Please try again.",
}

TERMINAL_PAYMENT_ERRORS = {"insufficient_balance", "invalid_amount"}

FALLBACK_RESPONSES: dict[ConversationState, str] = {
    ConversationState.GREETING: (
        "Hello! I'm here to help you with your payment. "
        "Could you please provide your account ID?"
    ),
    ConversationState.AWAITING_ACCOUNT_ID: (
        "Please provide your account ID (e.g., ACC1001)."
    ),
    ConversationState.AWAITING_NAME: (
        "Could you please provide your full name for verification?"
    ),
    ConversationState.AWAITING_SECONDARY: (
        "Please provide one of the following for verification:\n"
        "- Date of birth (YYYY-MM-DD)\n"
        "- Last 4 digits of your Aadhaar number\n"
        "- Your pincode"
    ),
    ConversationState.BALANCE_DISCLOSED: (
        "Would you like to make a payment? Please specify an amount or say 'full'."
    ),
    ConversationState.AWAITING_AMOUNT: "Please enter a payment amount.",
    ConversationState.COLLECTING_CARD: (
        "Please provide your card details:\n"
        "- Cardholder name\n- Card number\n- CVV\n- Expiry date (MM/YYYY)"
    ),
    ConversationState.PAYMENT_COMPLETE: "Thank you for your payment. Have a great day!",
    ConversationState.CLOSED: (
        "This session has ended. Please start a new conversation."
    ),
}


class Agent:
    """Payment collection agent using hybrid FSM + Claude API.

    State machine controls flow. Claude handles NLU (entity extraction)
    and NLG (response generation). Verification is strict and rule-based.
    PII never enters Claude's context.
    """

    def __init__(
        self,
        api_client: PaymentAPIClientBase | None = None,
        llm_client: LLMClientBase | None = None,
    ) -> None:
        self._api = api_client or PaymentAPIClient()
        self._llm = llm_client or ClaudeLLMClient()
        self._working = WorkingMemory()
        self._conv_memory = ConversationMemory()
        self._semantic = SemanticMemory()
        self._verifier = VerificationService()
        self._pii_scanner = PIIScanner()

    def next(self, user_input: str) -> dict:
        """Process one conversation turn."""
        self._working.turn_count += 1

        # Guardrail: session turn limit
        if self._working.turn_count > MAX_TURNS:
            self._close_session()
            return {"message": "Session expired. Please start a new conversation."}

        # Guardrail: truncate oversized input
        if len(user_input) > MAX_INPUT_LENGTH:
            user_input = user_input[:MAX_INPUT_LENGTH]

        # Store raw input for LLM extraction (Claude needs unredacted card data)
        self._conv_memory.add_user_message(user_input)

        # Get LLM response with extraction
        llm_response = self._call_llm()

        # Guardrail: redact card data from the user message we just added,
        # so subsequent LLM calls don't see raw PAN/CVV in history
        self._conv_memory.redact_last_user_message(_redact_card_data(user_input))

        # Process tool calls to extract entities
        extracted = self._process_tool_calls(llm_response)
        self._working.entity_buffer.fill(extracted)

        # State machine processes extractions in flow order
        response_text = self._run_state_machine(llm_response)

        # PII scan before returning
        response_text = self._pii_scanner.scan(
            response_text, self._working.account_data
        )

        self._conv_memory.add_assistant_message(response_text)
        return {"message": response_text}

    def _call_llm(self) -> LLMResponse:
        """Call Claude with state-specific prompt, context, and tools."""
        context_block = self._semantic.build_context_block()
        system = get_system_prompt(self._working.state, context_block)
        tools = get_tools_for_state(self._working.state)
        messages = self._conv_memory.get_messages_for_claude()

        try:
            response = self._llm.chat(system=system, messages=messages, tools=tools)

            # Handle tool_use stop_reason — Claude wants to call a tool
            if response.stop_reason == "tool_use" and response.tool_calls:
                tc = response.tool_calls[0]
                # Guardrail: redact card data from tool input before storing
                sanitized_input = dict(tc.input)
                if tc.name == "extract_card_details":
                    cn = sanitized_input.get("card_number")
                    if cn and len(str(cn)) >= 4:
                        sanitized_input["card_number"] = f"****{str(cn)[-4:]}"
                    if "cvv" in sanitized_input:
                        sanitized_input["cvv"] = "***"
                self._conv_memory.add_assistant_tool_use(
                    tc.id, tc.name, sanitized_input
                )
                self._conv_memory.add_tool_result(tc.id, "Entities extracted.")

                # Make a follow-up call for the text response
                follow_up = self._llm.chat(
                    system=system,
                    messages=self._conv_memory.get_messages_for_claude(),
                    tools=[],
                )
                return LLMResponse(
                    text=follow_up.text,
                    tool_calls=response.tool_calls,
                    stop_reason=follow_up.stop_reason,
                )

            return response
        except Exception:
            logger.exception("LLM call failed, using fallback")
            fallback = FALLBACK_RESPONSES.get(
                self._working.state, FALLBACK_RESPONSES[ConversationState.CLOSED]
            )
            return LLMResponse(text=fallback, tool_calls=[], stop_reason="fallback")

    def _process_tool_calls(self, response: LLMResponse) -> dict[str, Any]:
        """Extract entities from tool calls."""
        extracted: dict[str, Any] = {}
        for tc in response.tool_calls:
            if tc.name in ("extract_entities", "extract_card_details"):
                for key, value in tc.input.items():
                    if value is not None:
                        extracted[key] = value
        return extracted

    def _run_state_machine(self, llm_response: LLMResponse) -> str:
        """Process state transitions. Returns final response text."""
        state = self._working.state
        buf = self._working.entity_buffer

        # Check for decline intent in any state that supports it
        if buf.has_decline() and state in (
            ConversationState.BALANCE_DISCLOSED,
            ConversationState.AWAITING_AMOUNT,
            ConversationState.COLLECTING_CARD,
        ):
            self._close_session()
            return "No problem. Thank you for your time. Goodbye!"

        if state == ConversationState.GREETING:
            return self._handle_greeting(llm_response)
        elif state == ConversationState.AWAITING_ACCOUNT_ID:
            return self._handle_account_id(llm_response)
        elif state == ConversationState.AWAITING_NAME:
            return self._handle_name(llm_response)
        elif state == ConversationState.AWAITING_SECONDARY:
            return self._handle_secondary(llm_response)
        elif state == ConversationState.BALANCE_DISCLOSED:
            return self._handle_balance_response(llm_response)
        elif state == ConversationState.AWAITING_AMOUNT:
            return self._handle_amount(llm_response)
        elif state == ConversationState.COLLECTING_CARD:
            return self._handle_card(llm_response)
        elif state == ConversationState.PAYMENT_COMPLETE:
            self._close_session()
            return llm_response.text or "Thank you. Have a great day! Goodbye."
        elif state == ConversationState.CLOSED:
            return (
                "This session has ended. "
                "Please start a new conversation if you need further assistance."
            )
        return llm_response.text or FALLBACK_RESPONSES[ConversationState.CLOSED]

    def _close_session(self) -> None:
        """Clear sensitive data and transition to CLOSED."""
        self._working.state = ConversationState.CLOSED
        self._working.account_data = None
        self._working.card_details = CardDetails()
        self._working.collected_name = None

    # ---- State handlers ---- #

    def _handle_greeting(self, llm_response: LLMResponse) -> str:
        drained = self._working.entity_buffer.drain_for_state(
            ConversationState.AWAITING_ACCOUNT_ID
        )
        if "account_id" in drained:
            # Also capture any buffered name
            name_drained = self._working.entity_buffer.drain_for_state(
                ConversationState.AWAITING_NAME
            )
            if "name" in name_drained:
                self._working.collected_name = name_drained["name"]
            return self._do_account_lookup(drained["account_id"])

        self._working.state = ConversationState.AWAITING_ACCOUNT_ID
        return llm_response.text or FALLBACK_RESPONSES[ConversationState.GREETING]

    def _handle_account_id(self, llm_response: LLMResponse) -> str:
        drained = self._working.entity_buffer.drain_for_state(
            ConversationState.AWAITING_ACCOUNT_ID
        )
        if "account_id" not in drained:
            return (
                llm_response.text or "Please provide your account ID (e.g., ACC1001)."
            )

        # Capture any buffered name
        name_drained = self._working.entity_buffer.drain_for_state(
            ConversationState.AWAITING_NAME
        )
        if "name" in name_drained:
            self._working.collected_name = name_drained["name"]

        return self._do_account_lookup(drained["account_id"])

    def _do_account_lookup(self, account_id: str) -> str:
        account_data, error = self._api.lookup_account(account_id)
        if error:
            self._working.state = ConversationState.AWAITING_ACCOUNT_ID
            self._working.collected_name = None
            self._semantic.record(
                "error",
                f"Account lookup failed: {error}",
                self._working.turn_count,
            )
            return f"{error} Please try again with a valid account ID."

        self._working.account_id = account_id
        self._working.account_data = account_data
        self._semantic.record(
            "identity", f"Account {account_id} located", self._working.turn_count
        )

        # Check if name was buffered
        if self._working.collected_name:
            return self._try_verify_name(self._working.collected_name)

        self._working.state = ConversationState.AWAITING_NAME
        return (
            "Account found. For verification, could you please provide your full name?"
        )

    def _handle_name(self, llm_response: LLMResponse) -> str:
        drained = self._working.entity_buffer.drain_for_state(
            ConversationState.AWAITING_NAME
        )
        if "name" not in drained:
            return (
                llm_response.text or "Please provide your full name for verification."
            )
        return self._try_verify_name(drained["name"])

    def _try_verify_name(self, name: str) -> str:
        assert self._working.account_data is not None

        if self._verifier.verify_name(name, self._working.account_data):
            self._working.collected_name = name
            self._semantic.record(
                "identity",
                "User's name verified against records",
                self._working.turn_count,
            )

            # Check if secondary factor was buffered
            sec_drained = self._working.entity_buffer.drain_for_state(
                ConversationState.AWAITING_SECONDARY
            )
            if "factors" in sec_drained:
                self._working.state = ConversationState.AWAITING_SECONDARY
                return self._try_verify_secondary(sec_drained["factors"])

            self._working.state = ConversationState.AWAITING_SECONDARY
            return (
                "Thank you. To complete verification, please provide one of the following:\n"
                "- Date of birth (YYYY-MM-DD)\n"
                "- Last 4 digits of your Aadhaar number\n"
                "- Your pincode"
            )

        self._working.verification_attempts += 1
        remaining = MAX_VERIFICATION_ATTEMPTS - self._working.verification_attempts
        if remaining <= 0:
            self._close_session()
            self._semantic.record(
                "verification",
                "Session locked — max attempts exceeded",
                self._working.turn_count,
            )
            return (
                "Verification failed. Maximum attempts exceeded. "
                "For security, this session has been locked. "
                "Please contact customer support for assistance."
            )
        return (
            f"The name provided does not match our records. "
            f"You have {remaining} attempt(s) remaining. "
            f"Please provide your full name exactly as registered."
        )

    def _handle_secondary(self, llm_response: LLMResponse) -> str:
        drained = self._working.entity_buffer.drain_for_state(
            ConversationState.AWAITING_SECONDARY
        )
        if "factors" not in drained:
            return (
                llm_response.text
                or "Please provide your date of birth, last 4 of Aadhaar, or pincode."
            )
        return self._try_verify_secondary(drained["factors"])

    def _try_verify_secondary(self, factors: dict[str, str]) -> str:
        assert self._working.account_data is not None

        # Validate date format if DOB provided
        if "dob" in factors:
            valid, msg = validate_date_format(factors["dob"])
            if not valid:
                return f"{msg} Please provide your date of birth in YYYY-MM-DD format."

        if self._verifier.verify_secondary_factor(
            self._working.account_data,
            dob=factors.get("dob"),
            aadhaar_last4=factors.get("aadhaar_last4"),
            pincode=factors.get("pincode"),
        ):
            self._working.verified = True
            method = (
                "date of birth"
                if "dob" in factors
                else ("Aadhaar" if "aadhaar_last4" in factors else "pincode")
            )
            self._semantic.record(
                "verification",
                f"Verified via {method}",
                self._working.turn_count,
            )

            balance = self._working.account_data.balance
            self._semantic.record(
                "payment",
                f"Outstanding balance: {_fmt(balance)}",
                self._working.turn_count,
            )

            if balance <= 0:
                self._working.state = ConversationState.CLOSED
                return (
                    "Identity verified successfully! "
                    f"Your outstanding balance is {_fmt(balance)}. "
                    "No payment is required. Thank you!"
                )

            # Check buffered payment intent
            pay_drained = self._working.entity_buffer.drain_for_state(
                ConversationState.BALANCE_DISCLOSED
            )

            self._working.state = ConversationState.BALANCE_DISCLOSED

            if "amount" in pay_drained:
                return self._try_set_amount(pay_drained["amount"], balance)
            if "payment_intent" in pay_drained and pay_drained["payment_intent"] in (
                "full",
                "all",
                "entire",
            ):
                return self._try_set_amount(balance, balance)

            return (
                "Identity verified successfully! "
                f"Your outstanding balance is {_fmt(balance)}. "
                "Would you like to make a payment? If so, please specify the amount "
                "or say 'full' to pay the entire balance."
            )

        self._working.verification_attempts += 1
        remaining = MAX_VERIFICATION_ATTEMPTS - self._working.verification_attempts
        if remaining <= 0:
            self._close_session()
            self._semantic.record(
                "verification",
                "Session locked — max attempts exceeded",
                self._working.turn_count,
            )
            return (
                "Verification failed. Maximum attempts exceeded. "
                "For security, this session has been locked. "
                "Please contact customer support for assistance."
            )
        return (
            f"The information provided does not match our records. "
            f"You have {remaining} attempt(s) remaining. "
            "Please try again with one of:\n"
            "- Date of birth (YYYY-MM-DD)\n"
            "- Last 4 digits of Aadhaar\n"
            "- Pincode"
        )

    # ---- Payment ---- #

    def _handle_balance_response(self, llm_response: LLMResponse) -> str:
        assert self._working.account_data is not None
        balance = self._working.account_data.balance
        buf = self._working.entity_buffer

        drained = buf.drain_for_state(ConversationState.BALANCE_DISCLOSED)
        if "amount" in drained:
            return self._try_set_amount(drained["amount"], balance)
        if "payment_intent" in drained and drained["payment_intent"] in (
            "full",
            "all",
            "entire",
        ):
            return self._try_set_amount(balance, balance)

        if buf.has_affirmative():
            self._working.state = ConversationState.AWAITING_AMOUNT
            return f"How much would you like to pay? Your outstanding balance is {_fmt(balance)}."

        return (
            llm_response.text
            or "Would you like to make a payment? Please enter an amount or say 'no' to decline."
        )

    def _handle_amount(self, llm_response: LLMResponse) -> str:
        assert self._working.account_data is not None
        balance = self._working.account_data.balance

        drained = self._working.entity_buffer.drain_for_state(
            ConversationState.AWAITING_AMOUNT
        )
        if "amount" in drained:
            return self._try_set_amount(drained["amount"], balance)
        if "payment_intent" in drained and drained["payment_intent"] in (
            "full",
            "all",
            "entire",
        ):
            return self._try_set_amount(balance, balance)

        return llm_response.text or "Please enter a valid payment amount."

    def _try_set_amount(self, amount: float, balance: float) -> str:
        valid, error = validate_amount(amount, balance)
        if not valid:
            return f"{error} Please enter a valid amount (up to {_fmt(balance)})."

        self._working.payment_amount = amount
        self._working.state = ConversationState.COLLECTING_CARD
        self._semantic.record(
            "payment", f"Payment amount: {_fmt(amount)}", self._working.turn_count
        )
        return (
            f"You'd like to pay {_fmt(amount)}. Please provide your card details:\n"
            "- Cardholder name\n"
            "- Card number\n"
            "- CVV\n"
            "- Expiry date (MM/YYYY)"
        )

    def _handle_card(self, llm_response: LLMResponse) -> str:
        drained = self._working.entity_buffer.drain_for_state(
            ConversationState.COLLECTING_CARD
        )
        card = self._working.card_details

        if "card_fragments" in drained:
            frags = drained["card_fragments"]
            if "cardholder_name" in frags:
                card.cardholder_name = str(frags["cardholder_name"])
            if "card_number" in frags:
                card.card_number = str(frags["card_number"])
            if "cvv" in frags:
                card.cvv = str(frags["cvv"])
            if "expiry_month" in frags:
                card.expiry_month = int(frags["expiry_month"])
            if "expiry_year" in frags:
                card.expiry_year = int(frags["expiry_year"])

        if not card.is_complete():
            missing = card.missing_fields()
            return f"I still need the following: {', '.join(missing)}."

        # Validate card fields
        valid, result = validate_card_number(card.card_number)  # type: ignore[arg-type]
        if not valid:
            card.card_number = None
            return f"{result} Please provide a valid card number."
        card.card_number = result

        valid, result = validate_cvv(card.cvv, card.card_number)  # type: ignore[arg-type]
        if not valid:
            card.cvv = None
            return f"{result} Please provide a valid CVV."

        valid, result = validate_expiry(card.expiry_month, card.expiry_year)  # type: ignore[arg-type]
        if not valid:
            card.expiry_month = None
            card.expiry_year = None
            return f"{result} Please provide a valid expiry date (MM/YYYY)."

        return self._process_payment()

    def _process_payment(self) -> str:
        assert self._working.account_id is not None
        assert self._working.payment_amount is not None
        assert self._working.account_data is not None

        card = self._working.card_details
        success, txn_id, error_code = self._api.process_payment(
            self._working.account_id,
            self._working.payment_amount,
            card.to_api_dict(),
        )

        if success and txn_id:
            self._working.card_details = CardDetails()
            self._working.transaction_id = txn_id
            self._working.state = ConversationState.PAYMENT_COMPLETE
            remaining = (
                self._working.account_data.balance - self._working.payment_amount
            )
            self._semantic.record(
                "payment",
                f"Payment successful: {txn_id}",
                self._working.turn_count,
            )
            return (
                f"Payment successful!\n\n"
                f"Transaction Summary:\n"
                f"- Account: {self._working.account_id}\n"
                f"- Amount paid: {_fmt(self._working.payment_amount)}\n"
                f"- Transaction ID: {txn_id}\n"
                f"- Remaining balance: {_fmt(remaining)}\n\n"
                "Thank you for your payment!"
            )

        self._working.payment_attempts += 1
        error_msg = PAYMENT_ERROR_MESSAGES.get(
            error_code or "", PAYMENT_ERROR_MESSAGES["unknown_error"]
        )

        if error_code in TERMINAL_PAYMENT_ERRORS:
            self._close_session()
            return f"Payment failed: {error_msg} Session closed."

        if self._working.payment_attempts >= MAX_PAYMENT_ATTEMPTS:
            self._close_session()
            return (
                f"Payment failed: {error_msg} "
                "Maximum payment attempts exceeded. Please contact customer support."
            )

        if error_code == "invalid_card":
            self._working.card_details.card_number = None
        elif error_code == "invalid_cvv":
            self._working.card_details.cvv = None
        elif error_code == "invalid_expiry":
            self._working.card_details.expiry_month = None
            self._working.card_details.expiry_year = None

        remaining_attempts = MAX_PAYMENT_ATTEMPTS - self._working.payment_attempts
        return (
            f"Payment failed: {error_msg} "
            f"You have {remaining_attempts} attempt(s) remaining. "
            "Please provide the corrected details."
        )
