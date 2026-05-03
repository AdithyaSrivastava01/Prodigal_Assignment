# Design Document

## Architecture Overview

The agent uses a **hybrid FSM + Claude API** architecture. A deterministic state machine controls conversation flow, verification gates, and PII isolation, while Claude handles natural language understanding (entity extraction via `tool_use`) and natural language generation (conversational responses).

```
                     ┌──────────────────────────┐
                     │         Agent             │
                     │  (Hybrid FSM + Claude)    │
                     └────────────┬─────────────┘
          ┌───────────────┬───────┼───────┬───────────────┐
          │               │       │       │               │
   ┌──────▼──────┐ ┌─────▼─────┐ │ ┌─────▼──────┐ ┌─────▼──────┐
   │  LLM Client  │ │  Memory   │ │ │ Verification│ │ Validators  │
   │  (Claude API)│ │ (3-tier)  │ │ │  Service    │ │(Card, Date) │
   └──────┬──────┘ └───────────┘ │ └────────────┘ └────────────┘
          │                      │
   ┌──────▼──────┐        ┌─────▼──────┐
   │ Tool Defs    │        │  API Client │
   │ + Prompts    │        │  (Abstract) │
   │ + PIIScanner │        └─────┬──────┘
   └─────────────┘               │
                          ┌──────▼──────┐
                          │  httpx impl  │
                          └─────────────┘
```

### Why Hybrid, Not Full-LLM or Full-Rule-Based

- **Full-LLM risk:** An unconstrained LLM could skip verification steps, leak PII via prompt injection, or produce non-deterministic verification behavior. These are unacceptable in a payment flow.
- **Full-rule-based limitation:** Regex parsing is brittle — it misses phrasing variations and can't handle out-of-order input naturally. An LLM excels at understanding diverse input.
- **Hybrid advantage:** The state machine enforces invariants (verification gate, step ordering, retry limits), while Claude handles the "messy" parts (parsing "my birthday is May 14th 1990" or "I want to pay the full amount").

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

## Memory Architecture (3-Tier)

Inspired by mem0's extract-consolidate-retrieve pipeline and LangGraph's reducer-driven state:

| Tier | Class | Purpose | Mutability |
|------|-------|---------|-----------|
| 1 | `WorkingMemory` | Structured state — source of truth for FSM | Read/write by state machine |
| 2 | `ConversationMemory` | Sliding window + summary for Claude context | Append-only messages |
| 3 | `SemanticMemory` | Extracted facts injected into system prompt | Append-only facts |

**EntityBuffer** (part of WorkingMemory) handles slot-filling for out-of-order input. When a user says "Hi, I'm Nithin Jain, my account is ACC1001", both the name and account_id are buffered. The state machine drains entities in flow order — account_id first, then name — so no information is lost.

## PII Safety (Defense-in-Depth)

Three layers of protection:

1. **Architecture-level isolation:** DOB, Aadhaar last 4, and pincode are NEVER sent to Claude. The state machine performs verification locally using `VerificationService`. Claude only sees sanitized status messages ("Entities extracted.").

2. **System prompt rules:** Every state-specific prompt includes hard rules: "NEVER reveal the user's date of birth, Aadhaar number, or pincode."

3. **Post-response PIIScanner:** Before any response reaches the user, `PIIScanner` checks for leaked sensitive values. If found, the entire response is replaced with a safe fallback.

## LLM Integration

### Entity Extraction via Tool Use

Claude extracts entities through two tools with strict schemas:
- `extract_entities` — account_id, name, DOB, Aadhaar, pincode, payment amount/intent, decline/affirmative signals
- `extract_card_details` — cardholder name, card number, CVV, expiry

Progressive tool disclosure: only tools valid for the current state are exposed. Card collection state gets `extract_card_details`; terminal states get no tools.

### State-Specific System Prompts

Each `ConversationState` maps to a focused system prompt that tells Claude exactly what to do in that state. This prevents hallucination of irrelevant actions.

### Deterministic Fallback Chain

If the Claude API fails (rate limit, network error, server error):
1. Retry with exponential backoff + jitter (up to 3 attempts)
2. Fall back to template responses (one per state)
3. The conversation continues — never crashes

## Key Decisions

### 1. Case-Sensitive Exact Name Matching

`provided_name == account_data.full_name` with no normalization. The assignment requires strict matching with no fuzzy workarounds.

### 2. Shared Verification Counter

A single counter tracks failures across name AND secondary factor verification (max 3 total). Separate counters would allow 6 attempts — too lenient for security.

### 3. Dependency Injection for Both API and LLM

`PaymentAPIClientBase` and `LLMClientBase` are abstract. `MockLLMClient` returns pre-configured `LLMResponse` objects for deterministic unit testing. No LLM calls in unit tests.

### 4. Incremental Card Detail Collection

Card fields are merged across messages. Users can provide all details at once or one at a time.

## Testing Strategy (3 Layers)

| Layer | Location | What | Speed |
|-------|----------|------|-------|
| Unit | `tests/unit/` | State transitions with MockLLMClient, memory, PII scanner | <0.3s |
| Integration | `tests/integration/` | Full flows with real Claude + real Prodigal API | ~30s |
| Eval | `eval/` | LLM-as-judge behavioral scoring across scenarios | ~60s |

## Tradeoffs Accepted

1. **Synchronous API calls** — acceptable for CLI, not for concurrent web server use.
2. **No card number masking in memory** — card data cleared after payment, but exists in plaintext during collection.
3. **Two LLM calls per turn** — tool_use response + follow-up text response. Could be optimized to single call.
4. **No conversation summarization** — overflow window exists but summary generation isn't triggered automatically (would require an additional LLM call).

## What I Would Improve With More Time

1. **Async support** — make both API client and LLM client async for web server use.
2. **Streaming responses** — use Claude's streaming API for better UX.
3. **Automatic conversation summarization** — trigger when overflow exceeds threshold.
4. **Rate limiting** — cooldown between verification attempts.
5. **Session timeout** — expire inactive sessions.
6. **Card tokenization** — never store raw card numbers, even temporarily.
7. **Observability** — structured logging, OpenTelemetry traces.
8. **Multi-language support** — i18n for user-facing messages.
