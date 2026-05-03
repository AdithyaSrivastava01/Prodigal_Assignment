"""Integration tests using real Claude API and real Prodigal API.

Run with: uv run pytest tests/integration/ -v -m integration
Requires: ANTHROPIC_API_KEY environment variable set.
"""

from __future__ import annotations

import os

import pytest

from payment_agent.agent import Agent

pytestmark = pytest.mark.integration
skip_no_key = pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"),
    reason="ANTHROPIC_API_KEY not set",
)


@skip_no_key
class TestHappyPathIntegration:
    def test_full_flow_dob(self):
        agent = Agent()
        r0 = agent.next("Hi")
        assert len(r0["message"]) > 0

        r1 = agent.next("My account ID is ACC1001")
        assert "name" in r1["message"].lower() or "verif" in r1["message"].lower()

        r2 = agent.next("Nithin Jain")
        msg2 = r2["message"].lower()
        assert (
            "date" in msg2 or "aadhaar" in msg2 or "pincode" in msg2 or "verif" in msg2
        )

        r3 = agent.next("My date of birth is 1990-05-14")
        assert "verified" in r3["message"].lower() or "balance" in r3["message"].lower()

        r4 = agent.next("I'd like to pay 500 rupees")
        assert "card" in r4["message"].lower() or "500" in r4["message"]

        r5 = agent.next(
            "Cardholder: Nithin Jain, Card: 4532015112830366, "
            "CVV: 123, Expiry: 12/2027"
        )
        assert (
            "success" in r5["message"].lower() or "transaction" in r5["message"].lower()
        )

    def test_verification_failure(self):
        agent = Agent()
        agent.next("Hello")
        agent.next("ACC1001")
        r = agent.next("John Doe")
        assert (
            "does not match" in r["message"].lower()
            or "attempt" in r["message"].lower()
        )

    def test_zero_balance(self):
        agent = Agent()
        agent.next("Hi")
        agent.next("ACC1003")
        agent.next("Priya Agarwal")
        r = agent.next("1992-08-10")
        assert "0.00" in r["message"] or "no payment" in r["message"].lower()

    def test_account_not_found(self):
        agent = Agent()
        agent.next("Hi")
        r = agent.next("ACC9999")
        assert (
            "not found" in r["message"].lower() or "try again" in r["message"].lower()
        )

    def test_leap_year_dob(self):
        agent = Agent()
        agent.next("Hi")
        agent.next("ACC1004")
        agent.next("Rahul Mehta")
        r = agent.next("1988-02-29")
        assert "verified" in r["message"].lower() or "balance" in r["message"].lower()


@skip_no_key
class TestPIISafetyIntegration:
    def test_no_pii_leaked(self):
        agent = Agent()
        responses = []
        for msg in ["Hi", "ACC1001", "Nithin Jain", "1990-05-14"]:
            responses.append(agent.next(msg)["message"])

        sensitive = ["4321", "400001"]  # aadhaar, pincode — MUST NOT appear
        for resp in responses:
            for val in sensitive:
                assert val not in resp, f"PII value '{val}' found in response"
