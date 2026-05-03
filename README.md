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

Runs 6 behavioral scenarios with LLM-as-judge scoring. Reports pass rate, average score, and PII leak rate.

## Architecture

See [DESIGN.md](DESIGN.md) for detailed architecture documentation.

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

## Sample Conversation

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

## Linting

```bash
uv run ruff check .
```
