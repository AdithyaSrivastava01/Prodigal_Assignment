"""Evaluation scenarios for the payment collection agent."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Step:
    user_input: str
    expect_keywords: list[str] = field(default_factory=list)
    reject_keywords: list[str] = field(default_factory=list)


@dataclass
class Scenario:
    name: str
    description: str
    steps: list[Step]


SCENARIOS: list[Scenario] = [
    Scenario(
        name="Happy path — DOB verification, partial payment",
        description="Full successful flow: lookup, verify with DOB, pay partial amount",
        steps=[
            Step("Hi", ["account"]),
            Step("ACC1001", ["name"]),
            Step("Nithin Jain", ["date of birth", "pincode"]),
            Step("1990-05-14", ["verified", "1,250.75"]),
            Step("500", ["card"]),
            Step(
                "Name: Nithin Jain, Card: 4532015112830366, CVV: 123, Expiry: 12/2027",
                ["successful", "transaction"],
                ["4321", "400001"],
            ),
        ],
    ),
    Scenario(
        name="Happy path — Aadhaar verification",
        description="Verify identity using Aadhaar last 4 digits",
        steps=[
            Step("Hi", ["account"]),
            Step("ACC1001", ["name"]),
            Step("Nithin Jain", ["date of birth", "pincode"]),
            Step("4321", ["verified"]),
        ],
    ),
    Scenario(
        name="Happy path — pincode verification",
        description="Verify identity using pincode",
        steps=[
            Step("Hi", ["account"]),
            Step("ACC1001", ["name"]),
            Step("Nithin Jain", ["date of birth", "pincode"]),
            Step("400001", ["verified"]),
        ],
    ),
    Scenario(
        name="Happy path — full balance payment",
        description="Pay the entire outstanding balance using 'full' keyword",
        steps=[
            Step("Hi", ["account"]),
            Step("ACC1001", ["name"]),
            Step("Nithin Jain", ["date of birth"]),
            Step("1990-05-14", ["verified", "1,250.75"]),
            Step("full", ["1,250.75", "card"]),
            Step(
                "Name: Nithin Jain, Card: 4532015112830366, CVV: 123, Expiry: 12/2027",
                ["successful"],
            ),
        ],
    ),
    Scenario(
        name="Verification failure — wrong name lockout",
        description="Three wrong names should lock the session",
        steps=[
            Step("Hi", ["account"]),
            Step("ACC1001", ["name"]),
            Step("Wrong Name", ["2 attempt"]),
            Step("Another Wrong", ["1 attempt"]),
            Step("Still Wrong", ["maximum", "locked"]),
        ],
    ),
    Scenario(
        name="Verification failure — wrong secondary factor",
        description="Correct name but three wrong secondary factors locks session",
        steps=[
            Step("Hi", ["account"]),
            Step("ACC1001", ["name"]),
            Step("Nithin Jain", ["date of birth"]),
            Step("1990-01-01", ["does not match", "2 attempt"]),
            Step("1111", ["does not match", "1 attempt"]),
            Step("000000", ["maximum", "locked"]),
        ],
    ),
    Scenario(
        name="Account not found",
        description="Non-existent account ID should prompt retry",
        steps=[
            Step("Hi", ["account"]),
            Step("ACC9999", ["account", "try again"]),
        ],
    ),
    Scenario(
        name="Zero balance — no payment needed",
        description="Account with zero balance should skip payment flow",
        steps=[
            Step("Hi", ["account"]),
            Step("ACC1003", ["name"]),
            Step("Priya Agarwal", ["date of birth"]),
            Step("1992-08-10", ["verified", "0.00", "no payment"]),
        ],
    ),
    Scenario(
        name="Leap year DOB — ACC1004",
        description="1988-02-29 is a valid leap year date",
        steps=[
            Step("Hi", ["account"]),
            Step("ACC1004", ["name"]),
            Step("Rahul Mehta", ["date of birth"]),
            Step("1988-02-29", ["verified", "3,200.50"]),
        ],
    ),
    Scenario(
        name="Long name — ACC1002",
        description="Handle long Indian name correctly",
        steps=[
            Step("Hi", ["account"]),
            Step("ACC1002", ["name"]),
            Step("Rajarajeswari Balasubramaniam", ["date of birth"]),
            Step("1985-11-23", ["verified", "540.00"]),
        ],
    ),
    Scenario(
        name="User declines payment",
        description="User says 'no' after balance disclosure",
        steps=[
            Step("Hi", ["account"]),
            Step("ACC1001", ["name"]),
            Step("Nithin Jain", ["date of birth"]),
            Step("1990-05-14", ["verified"]),
            Step("no", ["goodbye"]),
        ],
    ),
    Scenario(
        name="Account ID in greeting",
        description="Out-of-order: provide account ID with first message",
        steps=[
            Step("Hi, my account is ACC1001", ["name"]),
        ],
    ),
    Scenario(
        name="Sensitive data never exposed",
        description="DOB, Aadhaar, pincode must never appear in agent responses",
        steps=[
            Step("Hi", [], ["1990-05-14", "4321", "400001"]),
            Step("ACC1001", [], ["1990-05-14", "4321", "400001"]),
            Step("Nithin Jain", [], ["1990-05-14", "4321", "400001"]),
            Step("1990-05-14", [], ["4321", "400001"]),
        ],
    ),
]
