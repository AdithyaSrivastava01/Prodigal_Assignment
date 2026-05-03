from __future__ import annotations

from payment_agent.models import AccountData


FALLBACK_RESPONSE = (
    "I apologize, but I need to rephrase my response. "
    "Could you please repeat your last message?"
)


class PIIScanner:
    """Post-response PII filter. Defense-in-depth layer.

    Scans agent responses for any sensitive account data values
    (DOB, Aadhaar last 4, pincode) and replaces the response
    with a safe fallback if any are found.
    """

    def scan(self, response: str, account_data: AccountData | None) -> str:
        """Check response for PII leaks. Returns safe response."""
        if account_data is None:
            return response

        sensitive_values = [
            account_data.dob,
            account_data.aadhaar_last4,
            account_data.pincode,
        ]

        for value in sensitive_values:
            if value and value in response:
                return FALLBACK_RESPONSE

        return response
