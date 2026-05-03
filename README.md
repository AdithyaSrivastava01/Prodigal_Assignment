# Payment Collection AI Agent

A production-ready conversational AI agent that handles end-to-end payment collection: account lookup, identity verification, balance disclosure, and card payment processing.

## Setup

```bash
# Install dependencies
uv sync

# Or with pip
pip install -e ".[dev]"
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
# All tests
uv run pytest

# Verbose
uv run pytest -v

# Specific module
uv run pytest tests/test_agent.py
```

## Evaluation

```bash
uv run python -m eval.evaluate
```

Runs 13 scenarios covering happy paths, verification failures, payment failures, edge cases, and sensitive data leak checks.

## Linting

```bash
uv run ruff check .
```

## Architecture

See [DESIGN.md](DESIGN.md) for detailed architecture documentation.

**Module overview:**

| Module | Responsibility |
|--------|---------------|
| `agent.py` | State machine orchestrator with `next()` interface |
| `models.py` | Pydantic models for conversation state, account data, card details |
| `validators.py` | Input validation (Luhn, CVV, expiry, date, amount) |
| `verification.py` | Strict identity verification (name + secondary factor) |
| `input_parser.py` | Regex-based extraction from free-text input |
| `api_client.py` | Abstract API client + httpx implementation |

## Sample Conversations

### Successful End-to-End Payment

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

### Verification Failure (User Exhausts Retries)

```
You: Hi
Agent: Hello! I'm here to help you with your payment. Could you please provide your account ID?

You: ACC1001
Agent: Account found. For verification, could you please provide your full name?

You: John Doe
Agent: The name provided does not match our records. You have 2 attempt(s) remaining.
Please provide your full name exactly as registered.

You: Jane Doe
Agent: The name provided does not match our records. You have 1 attempt(s) remaining.
Please provide your full name exactly as registered.

You: Nobody
Agent: Verification failed. Maximum attempts exceeded. For security, this session has been
locked. Please contact customer support for assistance.
```

### Payment Failure (Invalid Card)

```
You: Hi
Agent: Hello! I'm here to help you with your payment. Could you please provide your account ID?

You: ACC1001
Agent: Account found. For verification, could you please provide your full name?

You: Nithin Jain
Agent: Thank you. To complete verification, please provide one of the following: ...

You: 4321
Agent: Identity verified successfully! Your outstanding balance is ₹1,250.75. ...

You: 500
Agent: You'd like to pay ₹500.00. Please provide your card details: ...

You: Name: Nithin Jain, Card: 1234567890123456, CVV: 123, Expiry: 12/2027
Agent: Card number is invalid. Please provide a valid card number.
```

### Edge Case: Zero Balance Account

```
You: Hi
Agent: Hello! I'm here to help you with your payment. Could you please provide your account ID?

You: ACC1003
Agent: Account found. For verification, could you please provide your full name?

You: Priya Agarwal
Agent: Thank you. To complete verification, please provide one of the following: ...

You: 1992-08-10
Agent: Identity verified successfully! Your outstanding balance is ₹0.00.
No payment is required. Thank you!
```
