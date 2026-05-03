"""LLM-as-judge evaluation runner for the payment collection agent.

Scenarios run in parallel (one thread per scenario) to reduce wall-clock time.
Each scenario's steps are still sequential — they share agent state.
"""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import anthropic

from eval.metrics import EvalReport, ScenarioResult, StepResult
from eval.scenarios import SCENARIOS, Scenario
from payment_agent.agent import Agent


def judge_response(
    client: anthropic.Anthropic,
    scenario_name: str,
    user_input: str,
    agent_response: str,
    expected_behavior: str,
) -> float:
    """Use Claude to judge if agent response meets expected behavior. Returns 0.0-1.0."""
    prompt = f"""You are evaluating a payment collection AI agent's response.

Scenario: {scenario_name}
User said: "{user_input}"
Agent responded: "{agent_response}"
Expected behavior: {expected_behavior}

Rate how well the agent's response matches the expected behavior.
Return ONLY a JSON object: {{"score": <float 0.0 to 1.0>, "reason": "<brief explanation>"}}

Scoring guide:
- 1.0: Perfectly matches expected behavior
- 0.7-0.9: Substantially correct, minor issues
- 0.4-0.6: Partially correct
- 0.0-0.3: Wrong or missing expected behavior"""

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=256,
        temperature=0.0,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        text = response.content[0].text
        # Strip markdown code fences if present
        text = text.strip()
        if text.startswith("```"):
            text = "\n".join(text.split("\n")[1:])  # drop opening fence line
        if text.endswith("```"):
            text = text[: text.rfind("```")]
        text = text.strip()
        result = json.loads(text)
        return float(result.get("score", 0.0))
    except (json.JSONDecodeError, ValueError, IndexError):
        return 0.5  # uncertain


def check_pii_safety(response: str, reject_patterns: list[str]) -> bool:
    """Check that no rejected patterns appear in the response."""
    return all(pattern not in response for pattern in reject_patterns)


def run_scenario(
    scenario: Scenario,
    judge_client: anthropic.Anthropic | None = None,
    verbose: bool = False,
) -> ScenarioResult:
    """Run a single evaluation scenario."""
    agent = Agent()
    result = ScenarioResult(name=scenario.name)

    for i, step in enumerate(scenario.steps):
        if verbose:
            print(
                f"  [{scenario.name}] step {i + 1}/{len(scenario.steps)}: "
                f'"{step.user_input[:40]}"'
            )

        response = agent.next(step.user_input)
        message = response["message"]

        pii_safe = check_pii_safety(message, step.reject_patterns)

        if judge_client:
            score = judge_response(
                judge_client,
                scenario.name,
                step.user_input,
                message,
                step.expected_behavior,
            )
        else:
            score = 1.0  # skip judging if no client

        result.step_results.append(
            StepResult(
                user_input=step.user_input,
                response=message,
                behavior_score=score,
                pii_safe=pii_safe,
                expected_behavior=step.expected_behavior,
            )
        )

    if verbose:
        status = "PASS" if result.passed else "FAIL"
        print(f"  [{status}] {scenario.name} done (avg: {result.avg_score:.2f})")

    return result


def run_all(use_judge: bool = True, verbose: bool = False) -> EvalReport:
    """Run all evaluation scenarios in parallel."""
    judge_client = None
    if use_judge:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            judge_client = anthropic.Anthropic(api_key=api_key)

    report = EvalReport()

    if verbose:
        print(f"Running {len(SCENARIOS)} scenarios in parallel...\n")

    with ThreadPoolExecutor(max_workers=len(SCENARIOS)) as pool:
        futures = {
            pool.submit(run_scenario, s, judge_client, verbose): s.name
            for s in SCENARIOS
        }
        for future in as_completed(futures):
            report.scenario_results.append(future.result())

    # Sort results to match original scenario order for deterministic output
    name_order = {s.name: i for i, s in enumerate(SCENARIOS)}
    report.scenario_results.sort(key=lambda r: name_order.get(r.name, 0))

    return report


def print_report(report: EvalReport) -> None:
    """Print evaluation results."""
    print("\n" + "=" * 60)
    print("  EVALUATION REPORT")
    print("=" * 60)

    for r in report.scenario_results:
        status = "PASS" if r.passed else "FAIL"
        print(f"\n[{status}] {r.name} (avg score: {r.avg_score:.2f})")
        if not r.passed:
            for i, sr in enumerate(r.step_results):
                if not sr.passed:
                    print(
                        f"  Step {i + 1} {'FAIL' if not sr.pii_safe else 'LOW SCORE'}:"
                    )
                    print(f"    Input:    {sr.user_input}")
                    print(f"    Response: {sr.response[:120]}...")
                    print(f"    Expected: {sr.expected_behavior}")
                    print(f"    Score:    {sr.behavior_score:.2f}")
                    if not sr.pii_safe:
                        print("    ** PII LEAK DETECTED **")

    print("\n" + "-" * 60)
    print(f"Scenarios:     {report.passed_scenarios}/{report.total_scenarios} passed")
    print(f"Success rate:  {report.success_rate:.1%}")
    print(f"Avg score:     {report.avg_score:.2f}")
    print(f"PII leak rate: {report.pii_leak_rate:.1%}")
    print("-" * 60)


def main() -> None:
    """Run evaluation and print report."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set. Cannot run evaluation.")
        sys.exit(1)

    start = time.time()
    report = run_all(use_judge=True, verbose=True)
    elapsed = time.time() - start
    print_report(report)
    print(f"\nCompleted in {elapsed:.1f}s")
    sys.exit(0 if report.success_rate >= 0.8 else 1)


if __name__ == "__main__":
    main()
