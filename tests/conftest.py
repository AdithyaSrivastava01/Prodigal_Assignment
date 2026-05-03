from __future__ import annotations

import pytest

from payment_agent.agent import Agent
from payment_agent.api_client import PaymentAPIClientBase
from payment_agent.models import AccountData

TEST_ACCOUNTS: dict[str, AccountData] = {
    "ACC1001": AccountData(
        account_id="ACC1001",
        full_name="Nithin Jain",
        dob="1990-05-14",
        aadhaar_last4="4321",
        pincode="400001",
        balance=1250.75,
    ),
    "ACC1002": AccountData(
        account_id="ACC1002",
        full_name="Rajarajeswari Balasubramaniam",
        dob="1985-11-23",
        aadhaar_last4="9876",
        pincode="400002",
        balance=540.00,
    ),
    "ACC1003": AccountData(
        account_id="ACC1003",
        full_name="Priya Agarwal",
        dob="1992-08-10",
        aadhaar_last4="2468",
        pincode="400003",
        balance=0.00,
    ),
    "ACC1004": AccountData(
        account_id="ACC1004",
        full_name="Rahul Mehta",
        dob="1988-02-29",
        aadhaar_last4="1357",
        pincode="400004",
        balance=3200.50,
    ),
}


class MockPaymentAPIClient(PaymentAPIClientBase):
    """Mock API client for testing. Uses in-memory test accounts."""

    def __init__(
        self,
        accounts: dict[str, AccountData] | None = None,
        payment_responses: list[tuple[bool, str | None, str | None]] | None = None,
    ) -> None:
        self._accounts = accounts if accounts is not None else TEST_ACCOUNTS
        self._payment_responses = payment_responses or [(True, "txn_mock_12345", None)]
        self._payment_call_idx = 0
        self.lookup_calls: list[str] = []
        self.payment_calls: list[dict] = []

    def lookup_account(self, account_id: str) -> tuple[AccountData | None, str | None]:
        self.lookup_calls.append(account_id)
        if account_id in self._accounts:
            return self._accounts[account_id], None
        return None, "No account found with the provided account_id."

    def process_payment(
        self, account_id: str, amount: float, card: dict
    ) -> tuple[bool, str | None, str | None]:
        self.payment_calls.append(
            {"account_id": account_id, "amount": amount, "card": card}
        )
        if self._payment_call_idx < len(self._payment_responses):
            resp = self._payment_responses[self._payment_call_idx]
            self._payment_call_idx += 1
            return resp
        return True, "txn_mock_default", None


@pytest.fixture
def mock_api() -> MockPaymentAPIClient:
    return MockPaymentAPIClient()


@pytest.fixture
def agent(mock_api: MockPaymentAPIClient) -> Agent:
    return Agent(api_client=mock_api)


def drive_conversation(agent: Agent, messages: list[str]) -> list[str]:
    """Helper: send a sequence of messages and collect agent responses."""
    return [agent.next(msg)["message"] for msg in messages]
