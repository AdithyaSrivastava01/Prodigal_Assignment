from __future__ import annotations

from payment_agent.models import AccountData


class VerificationService:
    """Strict identity verification against account data.

    Rules:
    - Full name: exact case-sensitive string match (no fuzzy matching)
    - Secondary factor: at least one of DOB, Aadhaar last 4, or pincode must match exactly
    """

    def verify_name(self, provided_name: str, account_data: AccountData) -> bool:
        """Exact case-sensitive match for full name."""
        return provided_name == account_data.full_name

    def verify_secondary_factor(
        self,
        account_data: AccountData,
        dob: str | None = None,
        aadhaar_last4: str | None = None,
        pincode: str | None = None,
    ) -> bool:
        """Check if at least one secondary factor matches exactly."""
        if dob is not None and dob == account_data.dob:
            return True
        if aadhaar_last4 is not None and aadhaar_last4 == account_data.aadhaar_last4:
            return True
        if pincode is not None and pincode == account_data.pincode:
            return True
        return False
