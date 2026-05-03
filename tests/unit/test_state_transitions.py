from __future__ import annotations

from payment_agent.models import ConversationState, LLMResponse
from tests.conftest import (
    MockPaymentAPIClient,
    build_agent,
    make_card_extraction_response,
    make_extraction_response,
    make_text_response,
)


def _greeting_response() -> LLMResponse:
    """LLM response for greeting — no entities extracted."""
    return make_text_response("Hello! Please provide your account ID.")


def _account_id_response(account_id: str) -> LLMResponse:
    """LLM extracts account_id."""
    return make_extraction_response(
        {
            "account_id": account_id,
            "full_name": None,
            "dob": None,
            "aadhaar_last4": None,
            "pincode": None,
            "payment_amount": None,
            "payment_intent": None,
            "is_decline": False,
            "is_affirmative": False,
        }
    )


def _name_response(name: str) -> LLMResponse:
    """LLM extracts full_name."""
    return make_extraction_response(
        {
            "account_id": None,
            "full_name": name,
            "dob": None,
            "aadhaar_last4": None,
            "pincode": None,
            "payment_amount": None,
            "payment_intent": None,
            "is_decline": False,
            "is_affirmative": False,
        }
    )


def _dob_response(dob: str) -> LLMResponse:
    """LLM extracts DOB."""
    return make_extraction_response(
        {
            "account_id": None,
            "full_name": None,
            "dob": dob,
            "aadhaar_last4": None,
            "pincode": None,
            "payment_amount": None,
            "payment_intent": None,
            "is_decline": False,
            "is_affirmative": False,
        }
    )


def _aadhaar_response(aadhaar: str) -> LLMResponse:
    return make_extraction_response(
        {
            "account_id": None,
            "full_name": None,
            "dob": None,
            "aadhaar_last4": aadhaar,
            "pincode": None,
            "payment_amount": None,
            "payment_intent": None,
            "is_decline": False,
            "is_affirmative": False,
        }
    )


def _pincode_response(pincode: str) -> LLMResponse:
    return make_extraction_response(
        {
            "account_id": None,
            "full_name": None,
            "dob": None,
            "aadhaar_last4": None,
            "pincode": pincode,
            "payment_amount": None,
            "payment_intent": None,
            "is_decline": False,
            "is_affirmative": False,
        }
    )


def _amount_response(amount: float) -> LLMResponse:
    return make_extraction_response(
        {
            "account_id": None,
            "full_name": None,
            "dob": None,
            "aadhaar_last4": None,
            "pincode": None,
            "payment_amount": amount,
            "payment_intent": None,
            "is_decline": False,
            "is_affirmative": False,
        }
    )


def _full_payment_response() -> LLMResponse:
    return make_extraction_response(
        {
            "account_id": None,
            "full_name": None,
            "dob": None,
            "aadhaar_last4": None,
            "pincode": None,
            "payment_amount": None,
            "payment_intent": "full",
            "is_decline": False,
            "is_affirmative": False,
        }
    )


def _decline_response() -> LLMResponse:
    return make_extraction_response(
        {
            "account_id": None,
            "full_name": None,
            "dob": None,
            "aadhaar_last4": None,
            "pincode": None,
            "payment_amount": None,
            "payment_intent": None,
            "is_decline": True,
            "is_affirmative": False,
        }
    )


def _card_response(
    name: str | None = None,
    number: str | None = None,
    cvv: str | None = None,
    month: int | None = None,
    year: int | None = None,
) -> LLMResponse:
    return make_card_extraction_response(
        {
            "cardholder_name": name,
            "card_number": number,
            "cvv": cvv,
            "expiry_month": month,
            "expiry_year": year,
            "is_decline": False,
        }
    )


# Each test builds its own agent with the exact sequence of mock LLM responses.
# Text-only responses (stop_reason="end_turn") consume 1 mock response.
# Tool-use responses (stop_reason="tool_use") consume 2: extraction + follow-up text.


class TestHappyPathDOB:
    def test_full_flow(self):
        agent = build_agent(
            [
                _greeting_response(),  # "Hi" → text only (1 call)
                _account_id_response("ACC1001"),  # "ACC1001" → tool_use (2 calls)
                make_text_response(""),
                _name_response("Nithin Jain"),  # "Nithin Jain" → tool_use (2 calls)
                make_text_response(""),
                _dob_response("1990-05-14"),  # "1990-05-14" → tool_use (2 calls)
                make_text_response(""),
                _amount_response(500.0),  # "500" → tool_use (2 calls)
                make_text_response(""),
                _card_response("Nithin Jain", "4532015112830366", "123", 12, 2027),
                make_text_response(""),  # card → tool_use (2 calls)
                make_text_response("Goodbye!"),  # "thanks" → text only (1 call)
            ]
        )
        r0 = agent.next("Hi")
        assert "account" in r0["message"].lower()

        r1 = agent.next("ACC1001")
        assert "name" in r1["message"].lower()

        r2 = agent.next("Nithin Jain")
        assert (
            "date of birth" in r2["message"].lower()
            or "aadhaar" in r2["message"].lower()
        )

        r3 = agent.next("1990-05-14")
        assert "verified" in r3["message"].lower()
        assert "1,250.75" in r3["message"]

        r4 = agent.next("500")
        assert "card" in r4["message"].lower()

        r5 = agent.next(
            "Name: Nithin Jain, Card: 4532015112830366, CVV: 123, Expiry: 12/2027"
        )
        assert (
            "successful" in r5["message"].lower()
            or "transaction" in r5["message"].lower()
        )

        agent.next("thanks")
        assert agent._working.state == ConversationState.CLOSED


class TestHappyPathAadhaar:
    def test_verify_with_aadhaar(self):
        agent = build_agent(
            [
                _greeting_response(),
                _account_id_response("ACC1001"),
                make_text_response(""),
                _name_response("Nithin Jain"),
                make_text_response(""),
                _aadhaar_response("4321"),
                make_text_response(""),
            ]
        )
        agent.next("Hi")
        agent.next("ACC1001")
        agent.next("Nithin Jain")
        r = agent.next("4321")
        assert "verified" in r["message"].lower()


class TestHappyPathPincode:
    def test_verify_with_pincode(self):
        agent = build_agent(
            [
                _greeting_response(),
                _account_id_response("ACC1001"),
                make_text_response(""),
                _name_response("Nithin Jain"),
                make_text_response(""),
                _pincode_response("400001"),
                make_text_response(""),
            ]
        )
        agent.next("Hi")
        agent.next("ACC1001")
        agent.next("Nithin Jain")
        r = agent.next("400001")
        assert "verified" in r["message"].lower()


class TestVerificationNameFailure:
    def test_wrong_name_lockout(self):
        agent = build_agent(
            [
                _greeting_response(),
                _account_id_response("ACC1001"),
                make_text_response(""),
                _name_response("Wrong Name"),
                make_text_response(""),
                _name_response("Another Wrong"),
                make_text_response(""),
                _name_response("Still Wrong"),
                make_text_response(""),
            ]
        )
        agent.next("Hi")
        agent.next("ACC1001")
        r2 = agent.next("Wrong Name")
        assert "2 attempt" in r2["message"]
        r3 = agent.next("Another Wrong")
        assert "1 attempt" in r3["message"]
        r4 = agent.next("Still Wrong")
        assert "locked" in r4["message"].lower() or "maximum" in r4["message"].lower()
        assert agent._working.state == ConversationState.CLOSED


class TestVerificationSecondaryFailure:
    def test_wrong_secondary_lockout(self):
        agent = build_agent(
            [
                _greeting_response(),
                _account_id_response("ACC1001"),
                make_text_response(""),
                _name_response("Nithin Jain"),
                make_text_response(""),
                _dob_response("1990-01-01"),
                make_text_response(""),
                _aadhaar_response("1111"),
                make_text_response(""),
                _pincode_response("000000"),
                make_text_response(""),
            ]
        )
        agent.next("Hi")
        agent.next("ACC1001")
        agent.next("Nithin Jain")
        r3 = agent.next("1990-01-01")
        assert "does not match" in r3["message"].lower()
        r4 = agent.next("1111")
        assert "does not match" in r4["message"].lower()
        r5 = agent.next("000000")
        assert "locked" in r5["message"].lower() or "maximum" in r5["message"].lower()
        assert agent._working.state == ConversationState.CLOSED


class TestAccountNotFound:
    def test_invalid_account(self):
        agent = build_agent(
            [
                _greeting_response(),
                _account_id_response("ACC9999"),
                make_text_response(""),
            ]
        )
        agent.next("Hi")
        r = agent.next("ACC9999")
        assert (
            "not found" in r["message"].lower()
            or "valid account" in r["message"].lower()
        )
        assert agent._working.state == ConversationState.AWAITING_ACCOUNT_ID


class TestZeroBalance:
    def test_no_payment_needed(self):
        agent = build_agent(
            [
                _greeting_response(),
                _account_id_response("ACC1003"),
                make_text_response(""),
                _name_response("Priya Agarwal"),
                make_text_response(""),
                _dob_response("1992-08-10"),
                make_text_response(""),
            ]
        )
        agent.next("Hi")
        agent.next("ACC1003")
        agent.next("Priya Agarwal")
        r = agent.next("1992-08-10")
        assert "verified" in r["message"].lower()
        assert "0.00" in r["message"]
        assert "no payment" in r["message"].lower()
        assert agent._working.state == ConversationState.CLOSED


class TestPaymentDecline:
    def test_user_declines(self):
        agent = build_agent(
            [
                _greeting_response(),
                _account_id_response("ACC1001"),
                make_text_response(""),
                _name_response("Nithin Jain"),
                make_text_response(""),
                _dob_response("1990-05-14"),
                make_text_response(""),
                _decline_response(),
                make_text_response(""),
            ]
        )
        agent.next("Hi")
        agent.next("ACC1001")
        agent.next("Nithin Jain")
        agent.next("1990-05-14")
        r = agent.next("no")
        assert "goodbye" in r["message"].lower() or "thank" in r["message"].lower()
        assert agent._working.state == ConversationState.CLOSED


class TestLeapYearDOB:
    def test_acc1004_leap_year(self):
        agent = build_agent(
            [
                _greeting_response(),
                _account_id_response("ACC1004"),
                make_text_response(""),
                _name_response("Rahul Mehta"),
                make_text_response(""),
                _dob_response("1988-02-29"),
                make_text_response(""),
            ]
        )
        agent.next("Hi")
        agent.next("ACC1004")
        agent.next("Rahul Mehta")
        r = agent.next("1988-02-29")
        assert "verified" in r["message"].lower()


class TestLongName:
    def test_acc1002_long_name(self):
        agent = build_agent(
            [
                _greeting_response(),
                _account_id_response("ACC1002"),
                make_text_response(""),
                _name_response("Rajarajeswari Balasubramaniam"),
                make_text_response(""),
                _dob_response("1985-11-23"),
                make_text_response(""),
            ]
        )
        agent.next("Hi")
        agent.next("ACC1002")
        agent.next("Rajarajeswari Balasubramaniam")
        r = agent.next("1985-11-23")
        assert "verified" in r["message"].lower()


class TestSensitiveDataNotExposed:
    def test_no_pii_in_responses(self):
        agent = build_agent(
            [
                _greeting_response(),
                _account_id_response("ACC1001"),
                make_text_response(""),
                _name_response("Nithin Jain"),
                make_text_response(""),
                _dob_response("1990-05-14"),
                make_text_response(""),
                _amount_response(500.0),
                make_text_response(""),
                _card_response("Nithin Jain", "4532015112830366", "123", 12, 2027),
                make_text_response(""),
            ]
        )
        responses = []
        for msg in [
            "Hi",
            "ACC1001",
            "Nithin Jain",
            "1990-05-14",
            "500",
            "Name: Nithin Jain, Card: 4532015112830366, CVV: 123, Expiry: 12/2027",
        ]:
            responses.append(agent.next(msg)["message"])

        sensitive = ["4321", "400001"]  # aadhaar_last4, pincode
        for resp in responses:
            for val in sensitive:
                assert val not in resp, f"PII '{val}' leaked in: {resp}"


class TestPaymentFailureRetry:
    def test_invalid_card_retry(self):
        api = MockPaymentAPIClient(
            payment_responses=[
                (False, None, "invalid_card"),
                (True, "txn_retry_ok", None),
            ]
        )
        agent = build_agent(
            [
                _greeting_response(),
                _account_id_response("ACC1001"),
                make_text_response(""),
                _name_response("Nithin Jain"),
                make_text_response(""),
                _dob_response("1990-05-14"),
                make_text_response(""),
                _amount_response(500.0),
                make_text_response(""),
                _card_response("Nithin Jain", "4532015112830366", "123", 12, 2027),
                make_text_response(""),
            ],
            api_client=api,
        )

        for msg in ["Hi", "ACC1001", "Nithin Jain", "1990-05-14", "500"]:
            agent.next(msg)

        r = agent.next(
            "Name: Nithin Jain, Card: 4532015112830366, CVV: 123, Expiry: 12/2027"
        )
        assert "failed" in r["message"].lower() or "invalid" in r["message"].lower()
        assert "attempt" in r["message"].lower()


class TestClosedSession:
    def test_no_further_processing(self):
        agent = build_agent(
            [
                _greeting_response(),
                _account_id_response("ACC1001"),
                make_text_response(""),
                _name_response("Wrong"),
                make_text_response(""),
                _name_response("Wrong"),
                make_text_response(""),
                _name_response("Wrong"),
                make_text_response(""),
                make_text_response(""),  # extra for post-closed
            ]
        )
        agent.next("Hi")
        agent.next("ACC1001")
        agent.next("Wrong")
        agent.next("Wrong")
        agent.next("Wrong")
        assert agent._working.state == ConversationState.CLOSED
        r = agent.next("ACC1001")
        assert "ended" in r["message"].lower()
