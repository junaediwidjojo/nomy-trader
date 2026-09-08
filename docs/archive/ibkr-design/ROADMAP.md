# Roadmap

Each milestone should be a reviewable release with documentation, tests, and an
approved ExecPlan.

## Milestone 1 — Domain contracts and synthetic scenarios

Define typed Event, Evidence, Decision, TradePlan, ThesisVersion, Order, Fill,
and reconciliation states. Implement no network, model, or broker calls. Add
valid and invalid synthetic scenarios.

## Milestone 2 — Historical scanner baseline

Implement provider-neutral bars, candidate filters, event deduplication, and a
reproducible deterministic baseline. Resolve initial `TBD` universe and trigger
parameters through experiments.

## Milestone 3 — Evidence tools

Add time-bounded news, SEC/company disclosure, peer, and market-context tools.
Record immutable provenance and test untrusted-content handling.

## Milestone 4 — Structured AI analyst

Add model adapter and validated event classification. Reject malformed outputs.
Evaluate using synthetic and labeled historical cases; no orders.

## Milestone 5 — Valuation and complete trade plans

Implement deterministic scenario calculations. Require entry, targets, stop,
duration, thesis, invalidations, evidence, and uncertainty.

## Milestone 6 — Thesis and position ledger

Add SQLite migrations, append-only thesis versions, state transitions, journal,
and simulated broker reconciliation.

## Milestone 7 — Backtesting and evaluation

Compare baselines and AI variants using point-in-time controls, modeled costs,
slippage sensitivity, drawdowns, and AI-quality metrics.

## Milestone 8 — IBKR read-only integration

Verify account entity, paper account, permissions, subscriptions, session
behavior, scanner availability, quotes, portfolio, orders, and reconciliation.
No order submission.

## Milestone 9 — IBKR paper execution

Add idempotent paper orders, acknowledgements, partial fills, protective orders,
disconnect behavior, and notifications. Paper credentials only.

## Milestone 10 — Automated paper position management

Add supervised scheduling, deterministic exits, event-triggered thesis review,
daily reporting, recovery runbooks, and multi-month shadow/paper evaluation.

Live trading is not part of this roadmap. It requires a separate explicitly
approved proposal after evaluation and operational gates.

