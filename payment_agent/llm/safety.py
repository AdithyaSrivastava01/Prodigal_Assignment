from __future__ import annotations

import re

from payment_agent.models import AccountData

FALLBACK_RESPONSE = (
    "I apologize, but I need to rephrase my response. "
    "Could you please repeat your last message?"
)


class PIIScanner:
    """Post-response PII filter. Defense-in-depth layer.

    Scans agent responses for sensitive account data values
    (DOB, Aadhaar last 4, pincode) using word-boundary matching
    and common reformatted variants. Replaces the full response
    with a safe fallback if any PII is detected.
    """

    def scan(self, response: str, account_data: AccountData | None) -> str:
        """Check response for PII leaks. Returns safe response."""
        if account_data is None:
            return response

        patterns: list[str] = []

        if account_data.dob:
            patterns.append(re.escape(account_data.dob))
            parts = account_data.dob.split("-")
            if len(parts) == 3:
                # DD/MM/YYYY and MM/DD/YYYY variants
                patterns.append(re.escape(f"{parts[2]}/{parts[1]}/{parts[0]}"))
                patterns.append(re.escape(f"{parts[1]}/{parts[2]}/{parts[0]}"))

        if account_data.aadhaar_last4:
            patterns.append(r"\b" + re.escape(account_data.aadhaar_last4) + r"\b")

        if account_data.pincode:
            patterns.append(r"\b" + re.escape(account_data.pincode) + r"\b")

        for pattern in patterns:
            if re.search(pattern, response):
                return FALLBACK_RESPONSE

        return response
