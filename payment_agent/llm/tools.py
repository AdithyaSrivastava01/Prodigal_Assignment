from __future__ import annotations

from payment_agent.models import ConversationState

EXTRACT_ENTITIES_TOOL: dict = {
    "name": "extract_entities",
    "description": (
        "Extract structured entities from the user's message. "
        "Return null for any entity not clearly present in the message. "
        "For names, extract the EXACT text the user provided — "
        "do not normalize or correct spelling. "
        "For dates, extract in YYYY-MM-DD format if possible — "
        "do NOT validate whether dates are real, just extract them verbatim. "
        "For aadhaar_last4, extract exactly 4 digits. "
        "For pincode, extract exactly 6 digits."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "account_id": {
                "type": ["string", "null"],
                "description": "Account ID in format ACC followed by digits (e.g., ACC1001)",
            },
            "full_name": {
                "type": ["string", "null"],
                "description": "User's full name exactly as they stated it",
            },
            "dob": {
                "type": ["string", "null"],
                "description": "Date of birth in YYYY-MM-DD format",
            },
            "aadhaar_last4": {
                "type": ["string", "null"],
                "description": "Last 4 digits of Aadhaar number",
            },
            "pincode": {
                "type": ["string", "null"],
                "description": "6-digit Indian postal pincode",
            },
            "payment_amount": {
                "type": ["number", "null"],
                "description": "Specific payment amount mentioned by user",
            },
            "payment_intent": {
                "type": ["string", "null"],
                "description": "Payment intent keyword: 'full', 'all', 'entire', or null",
            },
            "is_decline": {
                "type": "boolean",
                "description": "True if user is declining, cancelling, or refusing",
            },
            "is_affirmative": {
                "type": "boolean",
                "description": "True if user is confirming, agreeing, or saying yes",
            },
        },
        "required": [
            "account_id",
            "full_name",
            "dob",
            "aadhaar_last4",
            "pincode",
            "payment_amount",
            "payment_intent",
            "is_decline",
            "is_affirmative",
        ],
        "additionalProperties": False,
    },
}

EXTRACT_CARD_DETAILS_TOOL: dict = {
    "name": "extract_card_details",
    "description": (
        "Extract card payment details from the user's message. "
        "Return null for any field not clearly present. "
        "For card_number, extract digits only (remove spaces/dashes). "
        "For expiry, extract month (1-12) and year (4-digit)."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "cardholder_name": {
                "type": ["string", "null"],
                "description": "Name on the card",
            },
            "card_number": {
                "type": ["string", "null"],
                "description": "Card number — digits only, no spaces or dashes",
            },
            "cvv": {
                "type": ["string", "null"],
                "description": "3 or 4 digit security code",
            },
            "expiry_month": {
                "type": ["integer", "null"],
                "description": "Card expiry month (1-12)",
            },
            "expiry_year": {
                "type": ["integer", "null"],
                "description": "Card expiry year (4-digit, e.g. 2027)",
            },
            "is_decline": {
                "type": "boolean",
                "description": "True if user is cancelling or refusing to pay",
            },
        },
        "required": [
            "cardholder_name",
            "card_number",
            "cvv",
            "expiry_month",
            "expiry_year",
            "is_decline",
        ],
        "additionalProperties": False,
    },
}


def get_tools_for_state(state: ConversationState) -> list[dict]:
    """Return tools available for the given conversation state.

    lookup_account and process_payment are NEVER exposed to Claude —
    they are called deterministically by the state machine.
    """
    if state == ConversationState.COLLECTING_CARD:
        return [EXTRACT_CARD_DETAILS_TOOL]
    if state in (ConversationState.PAYMENT_COMPLETE, ConversationState.CLOSED):
        return []
    return [EXTRACT_ENTITIES_TOOL]
