from __future__ import annotations

import pytest

from payment_agent.agent import Agent
from payment_agent.models import ConversationState
from tests.conftest import MockPaymentAPIClient, TEST_ACCOUNTS, drive_conversation


class TestHappyPathDOB:
    def test_full_flow(self, agent: Agent):
        responses = drive_conversation(
            agent,
            [
                "Hi",
                "ACC1001",
                "Nithin Jain",
                "1990-05-14",
                "500",
                "Name: Nithin Jain, Card: 4532015112830366, CVV: 123, Expiry: 12/2027",
                "thanks",
            ],
        )
        assert "account" in responses[0].lower()
        assert "name" in responses[1].lower()
        assert (
            "date of birth" in responses[2].lower() or "aadhaar" in responses[2].lower()
        )
        assert "verified" in responses[3].lower()
        assert "1,250.75" in responses[3] or "1250.75" in responses[3]
        assert "card" in responses[4].lower()
        assert (
            "successful" in responses[5].lower()
            or "transaction" in responses[5].lower()
        )
        assert agent._ctx.state == ConversationState.CLOSED


class TestHappyPathAadhaar:
    def test_verify_with_aadhaar(self, agent: Agent):
        responses = drive_conversation(
            agent,
            [
                "Hi",
                "ACC1001",
                "Nithin Jain",
                "4321",
            ],
        )
        assert "verified" in responses[3].lower()


class TestHappyPathPincode:
    def test_verify_with_pincode(self, agent: Agent):
        responses = drive_conversation(
            agent,
            [
                "Hi",
                "ACC1001",
                "Nithin Jain",
                "400001",
            ],
        )
        assert "verified" in responses[3].lower()


class TestVerificationNameFailure:
    def test_wrong_name_lockout(self, agent: Agent):
        responses = drive_conversation(
            agent,
            [
                "Hi",
                "ACC1001",
                "Wrong Name",
                "Another Wrong",
                "Still Wrong",
            ],
        )
        assert "2 attempt" in responses[2]
        assert "1 attempt" in responses[3]
        assert "locked" in responses[4].lower() or "maximum" in responses[4].lower()
        assert agent._ctx.state == ConversationState.CLOSED


class TestVerificationSecondaryFailure:
    def test_wrong_secondary_lockout(self, agent: Agent):
        responses = drive_conversation(
            agent,
            [
                "Hi",
                "ACC1001",
                "Nithin Jain",
                "1990-01-01",
                "1111",
                "000000",
            ],
        )
        assert "does not match" in responses[3].lower()
        assert "does not match" in responses[4].lower()
        assert "locked" in responses[5].lower() or "maximum" in responses[5].lower()
        assert agent._ctx.state == ConversationState.CLOSED


class TestAccountNotFound:
    def test_invalid_account(self, agent: Agent):
        responses = drive_conversation(
            agent,
            [
                "Hi",
                "ACC9999",
            ],
        )
        assert (
            "not found" in responses[1].lower()
            or "valid account" in responses[1].lower()
        )
        assert agent._ctx.state == ConversationState.AWAITING_ACCOUNT_ID


class TestZeroBalance:
    def test_no_payment_needed(self):
        api = MockPaymentAPIClient()
        agent = Agent(api_client=api)
        responses = drive_conversation(
            agent,
            [
                "Hi",
                "ACC1003",
                "Priya Agarwal",
                "1992-08-10",
            ],
        )
        assert "verified" in responses[3].lower()
        assert "0.00" in responses[3]
        assert "no payment" in responses[3].lower()
        assert agent._ctx.state == ConversationState.CLOSED


class TestPartialPayment:
    def test_pay_less_than_balance(self, agent: Agent):
        responses = drive_conversation(
            agent,
            [
                "Hi",
                "ACC1001",
                "Nithin Jain",
                "1990-05-14",
                "100",
                "Name: Nithin Jain, Card: 4532015112830366, CVV: 123, Expiry: 12/2027",
            ],
        )
        assert "100.00" in responses[5]
        assert "successful" in responses[5].lower()


class TestFullBalancePayment:
    def test_pay_full(self, agent: Agent):
        responses = drive_conversation(
            agent,
            [
                "Hi",
                "ACC1001",
                "Nithin Jain",
                "1990-05-14",
                "full",
                "Name: Nithin Jain, Card: 4532015112830366, CVV: 123, Expiry: 12/2027",
            ],
        )
        assert "1,250.75" in responses[5] or "1250.75" in responses[5]


class TestPaymentFailureInvalidCard:
    def test_invalid_card_retry(self):
        api = MockPaymentAPIClient(
            payment_responses=[
                (False, None, "invalid_card"),
                (True, "txn_retry_ok", None),
            ]
        )
        agent = Agent(api_client=api)
        responses = drive_conversation(
            agent,
            [
                "Hi",
                "ACC1001",
                "Nithin Jain",
                "1990-05-14",
                "500",
                "Name: Nithin Jain, Card: 4532015112830366, CVV: 123, Expiry: 12/2027",
            ],
        )
        assert "invalid" in responses[5].lower() or "failed" in responses[5].lower()
        assert "attempt" in responses[5].lower()


class TestPaymentMaxRetries:
    def test_lockout_after_3_failures(self):
        api = MockPaymentAPIClient(
            payment_responses=[
                (False, None, "invalid_card"),
                (False, None, "invalid_card"),
                (False, None, "invalid_card"),
            ]
        )
        agent = Agent(api_client=api)
        drive_conversation(
            agent,
            [
                "Hi",
                "ACC1001",
                "Nithin Jain",
                "1990-05-14",
                "500",
                "Name: Nithin Jain, Card: 4532015112830366, CVV: 123, Expiry: 12/2027",
                "Card: 4111111111111111",
                "Card: 4111111111111111",
            ],
        )
        assert agent._ctx.state == ConversationState.CLOSED


class TestUserDeclinesPayment:
    def test_decline_at_balance(self, agent: Agent):
        responses = drive_conversation(
            agent,
            [
                "Hi",
                "ACC1001",
                "Nithin Jain",
                "1990-05-14",
                "no",
            ],
        )
        assert "goodbye" in responses[4].lower() or "thank" in responses[4].lower()
        assert agent._ctx.state == ConversationState.CLOSED


class TestAccountIdInGreeting:
    def test_out_of_order(self, agent: Agent):
        responses = drive_conversation(
            agent,
            [
                "Hi, my account is ACC1001",
            ],
        )
        assert "name" in responses[0].lower()
        assert agent._ctx.state == ConversationState.AWAITING_NAME


class TestCardDetailsIncremental:
    def test_provide_one_at_a_time(self, agent: Agent):
        responses = drive_conversation(
            agent,
            [
                "Hi",
                "ACC1001",
                "Nithin Jain",
                "1990-05-14",
                "500",
                "Name: Nithin Jain",
            ],
        )
        assert "still need" in responses[5].lower()
        r2 = agent.next("4532015112830366")["message"]
        assert "still need" in r2.lower()
        r3 = agent.next("CVV: 123")["message"]
        assert "still need" in r3.lower()
        r4 = agent.next("12/2027")["message"]
        assert "successful" in r4.lower()


class TestLeapYearDOB:
    def test_acc1004_leap_year(self):
        api = MockPaymentAPIClient()
        agent = Agent(api_client=api)
        responses = drive_conversation(
            agent,
            [
                "Hi",
                "ACC1004",
                "Rahul Mehta",
                "1988-02-29",
            ],
        )
        assert "verified" in responses[3].lower()


class TestLongName:
    def test_acc1002_long_name(self):
        api = MockPaymentAPIClient()
        agent = Agent(api_client=api)
        responses = drive_conversation(
            agent,
            [
                "Hi",
                "ACC1002",
                "Rajarajeswari Balasubramaniam",
                "1985-11-23",
            ],
        )
        assert "verified" in responses[3].lower()


class TestClosedSession:
    def test_no_further_processing(self, agent: Agent):
        drive_conversation(
            agent,
            [
                "Hi",
                "ACC1001",
                "Wrong Name",
                "Wrong Name",
                "Wrong Name",
            ],
        )
        assert agent._ctx.state == ConversationState.CLOSED
        resp = agent.next("ACC1001")["message"]
        assert "ended" in resp.lower()


class TestSensitiveDataNotExposed:
    def test_no_pii_in_responses(self, agent: Agent):
        responses = drive_conversation(
            agent,
            [
                "Hi",
                "ACC1001",
                "Nithin Jain",
                "1990-05-14",
                "500",
                "Name: Nithin Jain, Card: 4532015112830366, CVV: 123, Expiry: 12/2027",
            ],
        )
        sensitive_values = ["4321", "400001"]
        for resp in responses:
            for val in sensitive_values:
                assert (
                    val not in resp
                ), f"Sensitive value '{val}' leaked in response: {resp}"
