from __future__ import annotations

from payment_agent.api_client import PaymentAPIClient, PaymentAPIClientBase
from payment_agent.config import MAX_PAYMENT_ATTEMPTS, MAX_VERIFICATION_ATTEMPTS
from payment_agent.input_parser import InputParser
from payment_agent.models import CardDetails, ConversationContext, ConversationState
from payment_agent.validators import (
    validate_amount,
    validate_card_number,
    validate_cvv,
    validate_date_format,
    validate_expiry,
)
from payment_agent.verification import VerificationService

PAYMENT_ERROR_MESSAGES: dict[str, str] = {
    "invalid_amount": (
        "The payment amount is invalid. "
        "It must be a positive number with at most 2 decimal places."
    ),
    "insufficient_balance": "The payment amount exceeds your outstanding balance.",
    "invalid_card": "The card number is invalid. Please check and try again.",
    "invalid_cvv": "The CVV provided is invalid.",
    "invalid_expiry": "The card expiry date is invalid or the card has expired.",
    "network_error": "Unable to connect to the payment server. Please try again.",
    "unknown_error": "An unexpected error occurred. Please try again.",
}


class Agent:
    """Payment collection agent using a rule-based state machine.

    Exposes a single `next(user_input)` method that processes one
    conversation turn and returns {"message": str}.
    """

    def __init__(self, api_client: PaymentAPIClientBase | None = None) -> None:
        self._ctx = ConversationContext()
        self._api = api_client or PaymentAPIClient()
        self._verifier = VerificationService()
        self._parser = InputParser()
        self._handlers: dict[ConversationState, callable] = {
            ConversationState.GREETING: self._handle_greeting,
            ConversationState.AWAITING_ACCOUNT_ID: self._handle_account_id,
            ConversationState.AWAITING_NAME: self._handle_name,
            ConversationState.AWAITING_SECONDARY: self._handle_secondary,
            ConversationState.BALANCE_DISCLOSED: self._handle_balance_response,
            ConversationState.AWAITING_AMOUNT: self._handle_amount,
            ConversationState.COLLECTING_CARD: self._handle_card,
            ConversationState.PAYMENT_COMPLETE: self._handle_post_payment,
            ConversationState.CLOSED: self._handle_closed,
        }

    def next(self, user_input: str) -> dict:
        """Process one conversation turn.

        Args:
            user_input: The user's message as a plain string.

        Returns:
            {"message": str} — the agent's response to display.
        """
        handler = self._handlers.get(self._ctx.state)
        if handler is None:
            return {"message": "Session ended. Please start a new conversation."}
        message = handler(user_input.strip())
        return {"message": message}

    # ------------------------------------------------------------------ #
    #  State handlers                                                      #
    # ------------------------------------------------------------------ #

    def _handle_greeting(self, text: str) -> str:
        account_id = self._parser.extract_account_id(text)
        if account_id:
            return self._do_account_lookup(account_id)

        name = self._parser.extract_name_from_any(text)
        if name:
            self._ctx.collected_name = name

        self._ctx.state = ConversationState.AWAITING_ACCOUNT_ID
        return (
            "Hello! I'm here to help you with your payment. "
            "Could you please provide your account ID?"
        )

    def _handle_account_id(self, text: str) -> str:
        account_id = self._parser.extract_account_id(text)
        if not account_id:
            return (
                "I couldn't find a valid account ID. "
                "Please provide it in the format ACC followed by digits (e.g., ACC1001)."
            )
        return self._do_account_lookup(account_id)

    def _do_account_lookup(self, account_id: str) -> str:
        account_data, error = self._api.lookup_account(account_id)
        if error:
            self._ctx.state = ConversationState.AWAITING_ACCOUNT_ID
            return f"{error} Please try again with a valid account ID."

        self._ctx.account_id = account_id
        self._ctx.account_data = account_data

        if self._ctx.collected_name:
            return self._try_verify_name(self._ctx.collected_name)

        self._ctx.state = ConversationState.AWAITING_NAME
        return (
            "Account found. For verification, could you please provide your full name?"
        )

    # -- Verification -------------------------------------------------- #

    def _handle_name(self, text: str) -> str:
        name = self._parser.extract_name_from_context(text)
        if not name:
            return "Please provide your full name for verification."
        return self._try_verify_name(name)

    def _try_verify_name(self, name: str) -> str:
        assert self._ctx.account_data is not None

        if self._verifier.verify_name(name, self._ctx.account_data):
            self._ctx.collected_name = name
            self._ctx.state = ConversationState.AWAITING_SECONDARY
            return (
                "Thank you. To complete verification, please provide one of the following:\n"
                "- Date of birth (YYYY-MM-DD)\n"
                "- Last 4 digits of your Aadhaar number\n"
                "- Your pincode"
            )

        self._ctx.verification_attempts += 1
        remaining = MAX_VERIFICATION_ATTEMPTS - self._ctx.verification_attempts
        if remaining <= 0:
            self._ctx.state = ConversationState.CLOSED
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

    def _handle_secondary(self, text: str) -> str:
        factors = self._parser.extract_secondary_factors(text)
        if not factors:
            return (
                "I couldn't identify a valid verification factor. Please provide one of:\n"
                "- Date of birth (YYYY-MM-DD)\n"
                "- Last 4 digits of your Aadhaar number (4 digits)\n"
                "- Your pincode (6 digits)"
            )

        if "dob" in factors:
            valid, msg = validate_date_format(factors["dob"])
            if not valid:
                return f"{msg} Please provide your date of birth in YYYY-MM-DD format."

        assert self._ctx.account_data is not None

        if self._verifier.verify_secondary_factor(
            self._ctx.account_data,
            dob=factors.get("dob"),
            aadhaar_last4=factors.get("aadhaar_last4"),
            pincode=factors.get("pincode"),
        ):
            self._ctx.verified = True
            balance = self._ctx.account_data.balance

            if balance <= 0:
                self._ctx.state = ConversationState.CLOSED
                return (
                    "Identity verified successfully! "
                    f"Your outstanding balance is \u20b9{balance:.2f}. "
                    "No payment is required. Thank you!"
                )

            self._ctx.state = ConversationState.BALANCE_DISCLOSED
            return (
                "Identity verified successfully! "
                f"Your outstanding balance is \u20b9{balance:.2f}. "
                "Would you like to make a payment? If so, please specify the amount "
                "or say 'full' to pay the entire balance."
            )

        self._ctx.verification_attempts += 1
        remaining = MAX_VERIFICATION_ATTEMPTS - self._ctx.verification_attempts
        if remaining <= 0:
            self._ctx.state = ConversationState.CLOSED
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

    # -- Payment ------------------------------------------------------- #

    def _handle_balance_response(self, text: str) -> str:
        if self._parser.is_decline(text):
            self._ctx.state = ConversationState.CLOSED
            return "No problem. Thank you for your time. Goodbye!"

        assert self._ctx.account_data is not None
        balance = self._ctx.account_data.balance

        amount = self._parser.extract_amount(text, balance)
        if amount is not None:
            return self._try_set_amount(amount)

        if self._parser.is_affirmative(text):
            self._ctx.state = ConversationState.AWAITING_AMOUNT
            return (
                f"How much would you like to pay? "
                f"Your outstanding balance is \u20b9{balance:.2f}."
            )

        return (
            "Would you like to make a payment? "
            "Please enter an amount or say 'no' to decline."
        )

    def _handle_amount(self, text: str) -> str:
        if self._parser.is_decline(text):
            self._ctx.state = ConversationState.CLOSED
            return "No problem. Thank you for your time. Goodbye!"

        assert self._ctx.account_data is not None
        balance = self._ctx.account_data.balance

        amount = self._parser.extract_amount(text, balance)
        if amount is None:
            return "Please enter a valid payment amount."

        return self._try_set_amount(amount)

    def _try_set_amount(self, amount: float) -> str:
        assert self._ctx.account_data is not None
        balance = self._ctx.account_data.balance

        valid, error = validate_amount(amount, balance)
        if not valid:
            return f"{error} Please enter a valid amount (up to \u20b9{balance:.2f})."

        self._ctx.payment_amount = amount
        self._ctx.state = ConversationState.COLLECTING_CARD
        return (
            f"You'd like to pay \u20b9{amount:.2f}. Please provide your card details:\n"
            "- Cardholder name\n"
            "- Card number\n"
            "- CVV\n"
            "- Expiry date (MM/YYYY)"
        )

    def _handle_card(self, text: str) -> str:
        if self._parser.is_decline(text):
            self._ctx.state = ConversationState.CLOSED
            self._ctx.card_details = CardDetails()
            return "Payment cancelled. Thank you for your time. Goodbye!"

        parsed = self._parser.extract_card_details(text)
        card = self._ctx.card_details

        if "cardholder_name" in parsed:
            card.cardholder_name = str(parsed["cardholder_name"])
        if "card_number" in parsed:
            card.card_number = str(parsed["card_number"])
        if "cvv" in parsed:
            card.cvv = str(parsed["cvv"])
        if "expiry_month" in parsed:
            card.expiry_month = int(parsed["expiry_month"])
        if "expiry_year" in parsed:
            card.expiry_year = int(parsed["expiry_year"])

        if not card.is_complete():
            missing = card.missing_fields()
            return f"I still need the following: {', '.join(missing)}."

        # Validate all card fields before API call
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
        assert self._ctx.account_id is not None
        assert self._ctx.payment_amount is not None
        assert self._ctx.account_data is not None

        card = self._ctx.card_details
        success, txn_id, error_code = self._api.process_payment(
            self._ctx.account_id,
            self._ctx.payment_amount,
            card.to_api_dict(),
        )

        # Clear card data immediately after API call (security)
        self._ctx.card_details = CardDetails()

        if success and txn_id:
            self._ctx.transaction_id = txn_id
            self._ctx.state = ConversationState.PAYMENT_COMPLETE
            remaining_balance = (
                self._ctx.account_data.balance - self._ctx.payment_amount
            )
            return (
                f"Payment successful!\n\n"
                f"Transaction Summary:\n"
                f"- Account: {self._ctx.account_id}\n"
                f"- Amount paid: \u20b9{self._ctx.payment_amount:.2f}\n"
                f"- Transaction ID: {txn_id}\n"
                f"- Remaining balance: \u20b9{remaining_balance:.2f}\n\n"
                "Thank you for your payment!"
            )

        self._ctx.payment_attempts += 1
        error_msg = PAYMENT_ERROR_MESSAGES.get(
            error_code or "", "An unexpected error occurred."
        )

        terminal_errors = {"insufficient_balance"}
        if error_code in terminal_errors:
            self._ctx.state = ConversationState.CLOSED
            return f"Payment failed: {error_msg} Session closed."

        if self._ctx.payment_attempts >= MAX_PAYMENT_ATTEMPTS:
            self._ctx.state = ConversationState.CLOSED
            return (
                f"Payment failed: {error_msg} "
                "Maximum payment attempts exceeded. Please contact customer support."
            )

        remaining_attempts = MAX_PAYMENT_ATTEMPTS - self._ctx.payment_attempts
        return (
            f"Payment failed: {error_msg} "
            f"You have {remaining_attempts} attempt(s) remaining. "
            "Please provide the corrected details."
        )

    # -- Post-payment -------------------------------------------------- #

    def _handle_post_payment(self, text: str) -> str:
        self._ctx.state = ConversationState.CLOSED
        return "Thank you. Have a great day! Goodbye."

    def _handle_closed(self, text: str) -> str:
        return (
            "This session has ended. "
            "Please start a new conversation if you need further assistance."
        )
