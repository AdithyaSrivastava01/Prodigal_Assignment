# Payment Collection AI Agent

A production-ready conversational AI agent that handles end-to-end payment collection: account lookup, identity verification, balance disclosure, and card payment processing. Uses a hybrid FSM + Claude API architecture with three-tier memory, PII isolation, and deterministic fallbacks.

## Setup

```bash
# Install dependencies
uv sync

# Set API key
export ANTHROPIC_API_KEY='your-key-here'
```

## Usage

### Interactive CLI

```bash
uv run python cli.py
```

### Programmatic

```python
from payment_agent import Agent

agent = Agent()
response = agent.next("Hi")
print(response["message"])
```

## Running Tests

```bash
# Unit tests (no API key needed, <0.3s)
uv run pytest tests/unit/ tests/test_validators.py tests/test_verification.py tests/test_api_client.py -v

# Integration tests (requires ANTHROPIC_API_KEY)
uv run pytest tests/integration/ -v -m integration

# All tests
uv run pytest -v
```

## Evaluation

```bash
uv run python -m eval.evaluate
```

Runs 7 behavioral scenarios in parallel with LLM-as-judge scoring (Claude Haiku). Reports pass rate, average behavior score, and PII leak rate.

## Architecture

See [DESIGN.md](DESIGN.md) (also available as [DESIGN.docx](DESIGN.docx)) for detailed architecture documentation.

**Module overview:**

| Module | Responsibility |
|--------|---------------|
| `agent.py` | Hybrid FSM + Claude orchestrator with `next()` interface |
| `models.py` | Pydantic models for state, account data, card details, LLM response |
| `memory/` | Three-tier memory: WorkingMemory, ConversationMemory, SemanticMemory |
| `llm/client.py` | Claude API client with retry + MockLLMClient for testing |
| `llm/tools.py` | Tool definitions for entity extraction (strict schemas) |
| `llm/prompts.py` | State-specific system prompts with PII safety rules |
| `llm/safety.py` | Post-response PII scanner (defense-in-depth) |
| `validators.py` | Input validation (Luhn, CVV, expiry, date, amount) |
| `verification.py` | Strict identity verification (name + secondary factor) |
| `api_client.py` | Abstract API client + httpx implementation |

## Sample Conversations

### 1. Successful End-to-End Payment

```
You: Hi
Agent: Hello! I'm here to help you with your payment. Could you please provide your account ID?

You: ACC1001
Agent: Account found. For verification, could you please provide your full name?

You: Nithin Jain
Agent: Thank you. To complete verification, please provide one of the following:
- Date of birth (YYYY-MM-DD)
- Last 4 digits of your Aadhaar number
- Your pincode

You: 1990-05-14
Agent: Identity verified successfully! Your outstanding balance is ₹1,250.75. Would you like
to make a payment? If so, please specify the amount or say 'full' to pay the entire balance.

You: 500
Agent: You'd like to pay ₹500.00. Please provide your card details:
- Cardholder name
- Card number
- CVV
- Expiry date (MM/YYYY)

You: Name: Nithin Jain, Card: 4532015112830366, CVV: 123, Expiry: 12/2027
Agent: Payment successful!

Transaction Summary:
- Account: ACC1001
- Amount paid: ₹500.00
- Transaction ID: txn_1762510325322_l1fl4oy
- Remaining balance: ₹750.75

Thank you for your payment!
```

### 2. Verification Failure (Exhausted Retries)

```
You: Hello
Agent: Hello! I'm here to help you with your payment. Could you please provide your account ID?

You: ACC1001
Agent: Account found. For verification, could you please provide your full name?

You: John Doe
Agent: The name provided does not match our records. You have 2 attempt(s) remaining.
Please provide your full name exactly as registered.

You: Jane Smith
Agent: The name provided does not match our records. You have 1 attempt(s) remaining.
Please provide your full name exactly as registered.

You: Another Wrong Name
Agent: Verification failed. Maximum attempts exceeded. For security, this session has been
locked. Please contact customer support for assistance.
```

### 3. Payment Failure (Expired Card)

```
You: Hi
Agent: Hello! I'm here to help you with your payment. Could you please provide your account ID?

You: ACC1001
Agent: Account found. For verification, could you please provide your full name?

You: Nithin Jain
Agent: Thank you. To complete verification, please provide one of the following:
- Date of birth (YYYY-MM-DD)
- Last 4 digits of your Aadhaar number
- Your pincode

You: 1990-05-14
Agent: Identity verified successfully! Your outstanding balance is ₹1,250.75. Would you like
to make a payment?

You: full
Agent: You'd like to pay ₹1,250.75. Please provide your card details:
- Cardholder name
- Card number
- CVV
- Expiry date (MM/YYYY)

You: Name: Nithin Jain, Card: 4532015112830366, CVV: 123, Expiry: 01/2020
Agent: Card has expired. Please provide a valid expiry date (MM/YYYY).
```

### 4. Edge Case: Leap Year DOB + Zero Balance

```
You: Hi
Agent: Hello! I'm here to help you with your payment. Could you please provide your account ID?

You: ACC1004
Agent: Account found. For verification, could you please provide your full name?

You: Rahul Mehta
Agent: Thank you. To complete verification, please provide one of the following:
- Date of birth (YYYY-MM-DD)
- Last 4 digits of your Aadhaar number
- Your pincode

You: 1988-02-29
Agent: Identity verified successfully! Your outstanding balance is ₹3,200.50. Would you like
to make a payment?

---

You: Hi
Agent: Hello! I'm here to help you with your payment. Could you please provide your account ID?

You: ACC1003
Agent: Account found. For verification, could you please provide your full name?

You: Priya Agarwal
Agent: Thank you. To complete verification, please provide one of the following:
- Date of birth (YYYY-MM-DD)
- Last 4 digits of your Aadhaar number
- Your pincode

You: 1992-08-10
Agent: Identity verified successfully! Your outstanding balance is ₹0.00. No payment is
required. Thank you!
```

## Evaluation Approach

### What We Measure

| Metric | Definition |
|--------|-----------|
| Behavior score | LLM-as-judge (Haiku) rates each agent response 0.0-1.0 against expected behavior |
| PII safety | Reject-pattern check ensures DOB, Aadhaar, pincode never appear in responses |
| Step pass | Score >= 0.7 AND PII safe |
| Scenario pass | All steps pass |

### Test Coverage

| Scenario | Tests |
|----------|-------|
| Happy path (DOB verification + payment) | Unit + Integration + Eval |
| Happy path (Aadhaar verification) | Unit |
| Happy path (pincode verification) | Unit |
| Verification failure (name lockout) | Unit + Eval |
| Verification failure (secondary factor lockout) | Unit |
| Payment failure (expired card) | Eval |
| Payment failure (invalid card + retry) | Unit |
| Account not found | Unit + Eval |
| Zero balance (no payment needed) | Unit + Eval |
| Leap year DOB edge case | Unit + Eval |
| PII never exposed | Unit + Eval |
| Session closed (no further processing) | Unit |
| User declines payment | Unit |
| Long name (ACC1002) | Unit |

### Where the Agent Struggles

1. **Non-deterministic LLM responses:** Even with `temperature=0.0`, Claude's responses vary slightly across runs. The state machine and deterministic responses mitigate this, but LLM-generated text (follow-up messages) can differ run-to-run.

2. **Forced tool use on empty input:** With `tool_choice: "any"`, Claude must call the extraction tool even for messages like "Hi" where no entities exist. Entity format validation in the buffer catches hallucinated values, but occasionally the LLM may extract plausible-looking garbage.

3. **Two-call overhead:** Each turn with entity extraction requires two Claude API calls (tool_use + follow-up text), adding ~2-4s latency per turn. A production system would benefit from streaming or prompt optimization.

4. **Name matching is strict but fragile:** Exact case-sensitive matching means "nithin jain" fails for "Nithin Jain". This is per-spec but a real system would want configurable fuzzy matching.

5. **Card data transiently in memory:** Despite redaction in conversation memory and cleanup on close, full card details exist briefly in `WorkingMemory` during the payment processing step. A production system should use a tokenization service.

## Assumptions

1. The API base URL in the assignment PDF includes `/openapi/` which is the Swagger docs path. Actual API endpoints work at the root URL without `/openapi/`. The agent uses the corrected URL.

2. The assignment says "Do NOT skip steps even if the user volunteers information early" — interpreted as: buffer out-of-order info and process in flow order (account_id first, then name, then secondary factor), rather than ignoring volunteered information.

3. Shared verification counter across name and secondary factor (3 total attempts, not 3 per stage) — chosen for stronger security.

## Linting

```bash
uv run ruff check .
```
