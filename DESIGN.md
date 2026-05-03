# Design Document

## Architecture Overview

The agent uses a **rule-based state machine** pattern where each conversation state maps to a handler method. The `Agent` class orchestrates all components through dependency injection.

```
                        ┌─────────────────┐
                        │     Agent       │
                        │  (State Machine)│
                        └──────┬──────────┘
               ┌───────────────┼───────────────┐
               │               │               │
        ┌──────▼──────┐ ┌─────▼──────┐ ┌──────▼──────┐
        │ InputParser  │ │ Verification│ │  Validators  │
        │ (Extraction) │ │  Service    │ │ (Validation) │
        └─────────────┘ └────────────┘ └─────────────┘
                               │
                        ┌──────▼──────┐
                        │  API Client  │
                        │  (Abstract)  │
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │  httpx impl  │
                        │  (Concrete)  │
                        └─────────────┘
```

### State Machine

```
GREETING ──► AWAITING_ACCOUNT_ID ──► AWAITING_NAME ──► AWAITING_SECONDARY
                                                              │
                                          ┌───────────────────┘
                                          ▼
                                   BALANCE_DISCLOSED ──► AWAITING_AMOUNT
                                                              │
                                          ┌───────────────────┘
                                          ▼
                                    COLLECTING_CARD ──► PAYMENT_COMPLETE ──► CLOSED
```

Any verification or payment failure beyond the retry limit transitions directly to `CLOSED`.

## Key Decisions

### 1. Rule-Based vs. LLM-Driven

**Decision:** Rule-based state machine.

**Rationale:**
- **Determinism** — the assignment requires consistent, repeatable behavior across runs. LLM outputs are inherently non-deterministic.
- **Strict verification** — the requirement explicitly forbids fuzzy matching. A regex/comparison approach guarantees exact matching with zero risk of an LLM "interpreting" a close match as valid.
- **Testability** — 116 unit/integration tests run in <0.5s with full coverage of edge cases. LLM-based agents require expensive, flaky evaluation loops.
- **Zero external dependencies** — no API keys, no token costs, no latency from LLM inference. The agent runs entirely locally except for the payment API calls.
- **Security** — no risk of prompt injection causing the agent to leak sensitive data or skip verification steps.

### 2. Case-Sensitive Exact Name Matching

**Decision:** `provided_name == account_data.full_name` with no normalization beyond whitespace collapsing in the input parser.

**Rationale:** The assignment states "no fuzzy matching, no case-insensitive workarounds for names." This is the strictest interpretation. The input parser normalizes multiple spaces (`" ".join(name.split())`), but the comparison itself is exact.

**Tradeoff:** A user typing "nithin jain" instead of "Nithin Jain" will fail verification. This is intentional per requirements but could be a UX issue in production.

### 3. Shared Verification Counter

**Decision:** A single counter (`verification_attempts`) tracks failures across both name and secondary factor verification, with a maximum of 3 total failed attempts.

**Rationale:** Separate counters would allow up to 6 total attempts (3 name + 3 secondary), which is too lenient for a security-sensitive flow. A shared counter ensures the session locks after 3 failures regardless of which step fails.

### 4. Abstract API Client for Dependency Injection

**Decision:** `PaymentAPIClientBase` (ABC) with a concrete `PaymentAPIClient` (httpx) implementation. The `Agent` constructor accepts an optional `api_client` parameter.

**Rationale:** Enables testing with `MockPaymentAPIClient` without network calls. All 116 tests run in <0.5s. Also allows swapping implementations (e.g., async client) without changing the agent.

### 5. Incremental Card Detail Collection

**Decision:** Parse whatever card fields the user provides in each message, merge with previously collected fields, and ask for remaining fields.

**Rationale:** Users may provide all details at once ("Name: X, Card: Y, CVV: Z, Expiry: W") or one at a time. The agent handles both by tracking which fields are complete and only asking for what's missing.

### 6. Card Data Clearing Strategy

**Decision:** Clear ALL card data on successful payment or terminal failure. On retryable failures, clear only the problematic field (e.g., `invalid_card` clears just the card number).

**Rationale:** Minimizes sensitive data retention while allowing the user to fix only the invalid field without re-entering everything.

## Tradeoffs Accepted

1. **Regex-based parsing is brittle** — patterns like "my name is X" work for common phrases but miss unusual phrasing. A production system would use NLP or structured input forms.

2. **No conversation history logging** — the agent maintains state in memory but doesn't log conversations. Production systems need audit trails.

3. **Synchronous API calls** — `httpx.Client` blocks during API calls. Acceptable for a CLI agent but not for a web server handling concurrent users.

4. **No card number masking in memory** — while card data is cleared after payment, it exists in plaintext in `ConversationContext` during collection. Production systems would use tokenization.

5. **Amount formatting** — uses standard comma formatting (1,250.75) rather than Indian numbering (1,250.75 is the same for amounts under 1 lakh, but larger amounts would differ).

## What I Would Improve With More Time

1. **Structured input collection** — for card details, use a form-like prompt with clear field labels rather than free-text parsing.

2. **Conversation logging** — add structured logging for audit trails without persisting raw card data.

3. **Async support** — make the API client async for use in web server contexts.

4. **Rate limiting** — add cooldown between verification attempts to prevent brute-force attacks.

5. **Session timeout** — expire inactive sessions after a configurable duration.

6. **i18n** — support multiple languages for user-facing messages.

7. **Input sanitization** — while the current regex approach is injection-safe (no code execution), adding explicit sanitization would be defense-in-depth.

8. **Comprehensive card validation** — validate card number prefixes (Visa starts with 4, Mastercard with 5, etc.) and enforce Amex 15-digit length.

9. **More robust date parsing** — accept formats like "May 14, 1990" or "14/05/1990" and normalize to YYYY-MM-DD.

10. **Webhook/callback support** — notify external systems of successful payments.
