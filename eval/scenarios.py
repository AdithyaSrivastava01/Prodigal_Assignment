"""Evaluation scenarios with behavioral expectations."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Step:
    user_input: str
    expected_behavior: str
    reject_patterns: list[str] = field(default_factory=list)


@dataclass
class Scenario:
    name: str
    description: str
    steps: list[Step]
    expected_terminal_state: str = "closed"


SCENARIOS: list[Scenario] = [
    Scenario(
        name="Happy path — DOB verification, partial payment",
        description="Full successful flow with DOB verification and partial payment",
        steps=[
            Step("Hi", "Should greet and ask for account ID"),
            Step("ACC1001", "Should ask for full name for verification"),
            Step(
                "Nithin Jain",
                "Should ask for secondary verification factor (DOB, Aadhaar, or pincode)",
            ),
            Step(
                "1990-05-14",
                "Should confirm verification and show balance of 1,250.75",
                reject_patterns=["4321", "400001"],
            ),
            Step("500", "Should confirm amount of 500 and ask for card details"),
            Step(
                "Name: Nithin Jain, Card: 4532015112830366, CVV: 123, Expiry: 12/2027",
                "Should show payment success with transaction ID",
                reject_patterns=["4321", "400001"],
            ),
        ],
    ),
    Scenario(
        name="Verification failure — wrong name lockout",
        description="Three wrong names lock the session",
        steps=[
            Step("Hi", "Should greet and ask for account ID"),
            Step("ACC1001", "Should ask for name"),
            Step(
                "Wrong Name",
                "Should say name doesn't match, mention remaining attempts",
            ),
            Step(
                "Another Wrong",
                "Should say name doesn't match, mention remaining attempts",
            ),
            Step(
                "Still Wrong", "Should lock session, mention maximum attempts exceeded"
            ),
        ],
    ),
    Scenario(
        name="Zero balance — no payment needed",
        description="Account with zero balance skips payment",
        steps=[
            Step("Hi", "Should greet"),
            Step("ACC1003", "Should ask for name"),
            Step("Priya Agarwal", "Should ask for secondary factor"),
            Step(
                "1992-08-10", "Should verify and show zero balance, no payment required"
            ),
        ],
    ),
    Scenario(
        name="Leap year DOB edge case",
        description="1988-02-29 is valid leap year date",
        steps=[
            Step("Hi", "Should greet"),
            Step("ACC1004", "Should ask for name"),
            Step("Rahul Mehta", "Should ask for secondary factor"),
            Step(
                "1988-02-29", "Should verify successfully and show balance of 3,200.50"
            ),
        ],
    ),
    Scenario(
        name="Account not found",
        description="Invalid account ID prompts retry",
        steps=[
            Step("Hi", "Should greet"),
            Step("ACC9999", "Should say account not found, ask to try again"),
        ],
    ),
    Scenario(
        name="Sensitive data never exposed",
        description="PII must never appear in any response",
        steps=[
            Step("Hi", "Should greet", ["1990-05-14", "4321", "400001"]),
            Step("ACC1001", "Should ask for name", ["1990-05-14", "4321", "400001"]),
            Step(
                "Nithin Jain",
                "Should ask for secondary",
                ["1990-05-14", "4321", "400001"],
            ),
            Step("1990-05-14", "Should verify", ["4321", "400001"]),
        ],
    ),
]
