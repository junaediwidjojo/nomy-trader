# ADR 005: FMP discovery and Telegram recommendations

## Status

Scope direction requested by user on 2026-09-08; implementation ExecPlan pending
approval. Supersedes the MVP portions of ADRs 002 and 004, not their history.

## Decision

Replace IBKR data with FMP free-tier losers/screener and quote/history data.
Replace order submission with a persisted complete buy-side recommendation and
outbound Telegram message. User execution in another app is not integrated.
No broker read-only access, reconciliation, positions or automated exits in MVP.
Advisory stop/target/duration content remains required. Keep deterministic sizing
and validation; approve the treatment of unverifiable portfolio limits explicitly.

## Consequences

Persist recommendations/outbox and quota use early. Informal manual comparison
replaces formal AI-versus-baseline evaluation. Confirm/reject is a fast-follow.
Broker automation is deferred to a separate future proposal; original specs are
preserved in docs/archive/ibkr-design. The system does not enforce user trades.
FMP free-tier entitlement/freshness must be verified before scan policy is set.
