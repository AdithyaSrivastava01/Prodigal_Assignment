"""Automated evaluation runner for the payment collection agent."""

from __future__ import annotations

import sys
from dataclasses import dataclass, field

from payment_agent.agent import Agent
from payment_agent.api_client import PaymentAPIClientBase
from payment_agent.models import AccountData
from eval.scenarios import SCENARIOS, Scenario, Step


# ------------------------------------------------------------------ #
#  Mock client for evaluation (same test accounts as the real API)    #
# ------------------------------------------------------------------ #

_EVAL_ACCOUNTS: dict[str, AccountData] = {
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


class EvalAPIClient(PaymentAPIClientBase):
    def lookup_account(self, account_id: str) -> tuple[AccountData | None, str | None]:
        if account_id in _EVAL_ACCOUNTS:
            return _EVAL_ACCOUNTS[account_id], None
        return None, "No account found with the provided account_id."

    def process_payment(
        self, account_id: str, amount: float, card: dict
    ) -> tuple[bool, str | None, str | None]:
        return True, f"txn_eval_{account_id}_{int(amount * 100)}", None


# ------------------------------------------------------------------ #
#  Evaluation result types                                            #
# ------------------------------------------------------------------ #


@dataclass
class StepResult:
    user_input: str
    response: str
    keyword_pass: bool
    reject_pass: bool

    @property
    def passed(self) -> bool:
        return self.keyword_pass and self.reject_pass


@dataclass
class ScenarioResult:
    name: str
    step_results: list[StepResult] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return all(s.passed for s in self.step_results)

    @property
    def total_steps(self) -> int:
        return len(self.step_results)

    @property
    def passed_steps(self) -> int:
        return sum(1 for s in self.step_results if s.passed)


# ------------------------------------------------------------------ #
#  Runner                                                             #
# ------------------------------------------------------------------ #


def run_scenario(scenario: Scenario) -> ScenarioResult:
    agent = Agent(api_client=EvalAPIClient())
    result = ScenarioResult(name=scenario.name)

    for step in scenario.steps:
        response = agent.next(step.user_input)
        message = response["message"]

        keyword_pass = all(kw.lower() in message.lower() for kw in step.expect_keywords)
        reject_pass = all(
            kw.lower() not in message.lower() for kw in step.reject_keywords
        )

        result.step_results.append(
            StepResult(
                user_input=step.user_input,
                response=message,
                keyword_pass=keyword_pass,
                reject_pass=reject_pass,
            )
        )

    return result


def run_all() -> list[ScenarioResult]:
    return [run_scenario(s) for s in SCENARIOS]


def print_report(results: list[ScenarioResult]) -> None:
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    total_steps = sum(r.total_steps for r in results)
    passed_steps = sum(r.passed_steps for r in results)

    print("=" * 60)
    print("  EVALUATION REPORT")
    print("=" * 60)

    for r in results:
        status = "PASS" if r.passed else "FAIL"
        print(f"\n[{status}] {r.name}")
        if not r.passed:
            for i, sr in enumerate(r.step_results):
                if not sr.passed:
                    print(f"  Step {i + 1} FAILED:")
                    print(f"    Input: {sr.user_input}")
                    print(f"    Response: {sr.response[:120]}...")
                    if not sr.keyword_pass:
                        print("    -> Missing expected keywords")
                    if not sr.reject_pass:
                        print("    -> Contains rejected keywords (sensitive data leak)")

    print("\n" + "-" * 60)
    print(f"Scenarios: {passed}/{total} passed")
    print(f"Steps:     {passed_steps}/{total_steps} passed")
    print(f"Pass rate: {passed / total * 100:.1f}%")
    print("-" * 60)


def main() -> None:
    results = run_all()
    print_report(results)
    sys.exit(0 if all(r.passed for r in results) else 1)


if __name__ == "__main__":
    main()
