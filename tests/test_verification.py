from __future__ import annotations

from payment_agent.models import AccountData
from payment_agent.verification import VerificationService


def _make_account() -> AccountData:
    return AccountData(
        account_id="ACC1001",
        full_name="Nithin Jain",
        dob="1990-05-14",
        aadhaar_last4="4321",
        pincode="400001",
        balance=1250.75,
    )


class TestVerifyName:
    def setup_method(self):
        self.svc = VerificationService()
        self.account = _make_account()

    def test_exact_match(self):
        assert self.svc.verify_name("Nithin Jain", self.account) is True

    def test_case_mismatch_fails(self):
        assert self.svc.verify_name("nithin jain", self.account) is False

    def test_wrong_name(self):
        assert self.svc.verify_name("John Doe", self.account) is False

    def test_partial_name(self):
        assert self.svc.verify_name("Nithin", self.account) is False

    def test_extra_spaces_fails(self):
        assert self.svc.verify_name("Nithin  Jain", self.account) is False

    def test_leading_trailing_spaces_fails(self):
        assert self.svc.verify_name(" Nithin Jain ", self.account) is False


class TestVerifySecondaryFactor:
    def setup_method(self):
        self.svc = VerificationService()
        self.account = _make_account()

    def test_dob_match(self):
        assert self.svc.verify_secondary_factor(self.account, dob="1990-05-14") is True

    def test_dob_mismatch(self):
        assert self.svc.verify_secondary_factor(self.account, dob="1990-01-01") is False

    def test_aadhaar_match(self):
        assert (
            self.svc.verify_secondary_factor(self.account, aadhaar_last4="4321") is True
        )

    def test_aadhaar_mismatch(self):
        assert (
            self.svc.verify_secondary_factor(self.account, aadhaar_last4="9999")
            is False
        )

    def test_pincode_match(self):
        assert self.svc.verify_secondary_factor(self.account, pincode="400001") is True

    def test_pincode_mismatch(self):
        assert self.svc.verify_secondary_factor(self.account, pincode="000000") is False

    def test_no_factors_provided(self):
        assert self.svc.verify_secondary_factor(self.account) is False

    def test_multiple_factors_one_matches(self):
        assert (
            self.svc.verify_secondary_factor(
                self.account, dob="wrong", aadhaar_last4="4321"
            )
            is True
        )

    def test_multiple_factors_none_match(self):
        assert (
            self.svc.verify_secondary_factor(
                self.account, dob="wrong", aadhaar_last4="0000", pincode="000000"
            )
            is False
        )
