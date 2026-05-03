from __future__ import annotations

from payment_agent.llm.safety import PIIScanner
from payment_agent.models import AccountData


def _make_account() -> AccountData:
    return AccountData(
        account_id="ACC1001",
        full_name="Nithin Jain",
        dob="1990-05-14",
        aadhaar_last4="4321",
        pincode="400001",
        balance=1250.75,
    )


class TestPIIScanner:
    def setup_method(self):
        self.scanner = PIIScanner()
        self.account = _make_account()

    def test_clean_response_passes(self):
        response = "Your identity has been verified. Your balance is Rs.1,250.75."
        result = self.scanner.scan(response, self.account)
        assert result == response

    def test_dob_leaked_is_blocked(self):
        response = "Your date of birth is 1990-05-14."
        result = self.scanner.scan(response, self.account)
        assert "1990-05-14" not in result

    def test_aadhaar_leaked_is_blocked(self):
        response = "Your Aadhaar last 4 digits are 4321."
        result = self.scanner.scan(response, self.account)
        assert "4321" not in result

    def test_pincode_leaked_is_blocked(self):
        response = "Your pincode is 400001."
        result = self.scanner.scan(response, self.account)
        assert "400001" not in result

    def test_account_id_is_allowed(self):
        response = "Account ACC1001 has been verified."
        result = self.scanner.scan(response, self.account)
        assert "ACC1001" in result

    def test_balance_is_allowed(self):
        response = "Your outstanding balance is Rs.1,250.75."
        result = self.scanner.scan(response, self.account)
        assert "1,250.75" in result

    def test_full_name_is_allowed(self):
        response = "Thank you, Nithin Jain."
        result = self.scanner.scan(response, self.account)
        assert "Nithin Jain" in result

    def test_no_account_data_passes_through(self):
        response = "Hello! Please provide your account ID."
        result = self.scanner.scan(response, None)
        assert result == response

    def test_multiple_pii_values_all_blocked(self):
        response = "DOB: 1990-05-14, Aadhaar: 4321, Pincode: 400001"
        result = self.scanner.scan(response, self.account)
        assert "1990-05-14" not in result
        assert "4321" not in result
        assert "400001" not in result

    def test_fallback_message_returned_on_leak(self):
        response = "Your DOB is 1990-05-14."
        result = self.scanner.scan(response, self.account)
        # Should return a safe fallback, not empty string
        assert len(result) > 0
