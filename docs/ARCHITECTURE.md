# Architecture — FMP and Telegram MVP

Changed 2026-09-08; [original IBKR architecture](archive/ibkr-design/ARCHITECTURE.md)
is preserved for a separately approved future automation project.

One Python 3.12+ modular process developed on Mac, later supervised on Linux.
Use uv, Pydantic, SQLite, SQLAlchemy/Alembic, HTTP adapters, and exchange-calendar
scheduling. Document and lock dependencies when introduced. Keep OpenAI, FMP,
evidence and Telegram behind interfaces. No IB Gateway/TWS dependency.

```text
session scheduler -> FMP losers/screener -> quote/history eligibility checks
  -> evidence -> structured AI analyst -> deterministic valuation/advisory sizing
  -> complete plan validation -> SQLite recommendation + transactional outbox
  -> Telegram notification -> user independently decides and buys elsewhere
```

The application's responsibility ends at notification. No broker calls,
positions, reconciliation, automatic sell/stop/target evaluation or fill tracking.
No incoming Telegram confirmation loop. Stop, target and duration are advisory
plan fields only. Model tools cannot mutate the database or size positions.

## Data and scheduling

FMP replaces IBKR market scanning and quotes. Prefer market-wide discovery and
entitled batches; bound per-symbol enrichment. Independently recompute all
configured eligibility filters. Verify fields, entitlement and source timestamps;
missing required fields fail eligibility. Free-tier budget and freshness must be
verified before choosing cadence. See ExecPlan decisions D01–D03. Persist shared
quota reservations across every FMP consumer and restart, including failed calls.
Use caching without masking stale data; skip scans that exceed remaining budget.
Use exchange calendars, not fixed local market hours or catch-up bursts.

## Persistence and failure behavior

SQLite owns immutable recommendation/evidence/policy history and local delivery
intent, not actual holdings. Save full TradePlan and outbox atomically before
sending. SENT means Telegram acknowledged a message; it never means a trade.
A timeout/crash after dispatch is UNKNOWN and is not automatically resent.
Expose failed/unknown delivery in CLI; preserve attempt history. Check plan age
again before delivery. Database failure prevents send; stale data, missing risk
inputs, malformed model output and insufficient evidence prevent recommendations.
FMP exhaustion pauses calls until the verified budget reset.

## Security and operational boundary

Tokens and private destination/capital settings stay outside version control.
Redact query keys and token-bearing URLs. Retrieved content is inert untrusted
input. Supervision restarts the process without resetting quota or duplicating
queued recommendations. Reports cover recommendations and operational health,
never inferred positions or returns. Formal evaluation and broker recovery are
deferred; the MVP has no exposure data with which to enforce portfolio limits.
