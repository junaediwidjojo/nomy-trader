# Read-only IBKR sudden-sell investigation ExecPlan

Status: proposed 2026-09-09. Implement only after approval. This is a bounded
market-data experiment; it does not restore the archived IBKR execution design.

## 1. Goal and user-visible outcome

Explain a shortlisted stock's sudden decline at the correct market time before
considering a manual buy. The result is an auditable incident report with its
decline window, time-stamped price/volume behavior, primary-source events,
competing explanations, uncertainty, and `REJECT`, `WATCH`, or
`MANUAL_BUY_CANDIDATE` outcome. IBKR supplies read-only data only.

## 2. Scope and explicit non-goals

In scope: provider-neutral dislocation investigation, read-only IBKR historical
bars and one entitled quote observation, immutable provenance, event-time
alignment, and blocking price guidance when data is stale or incomplete.

Out of scope: positions, cash, orders, fills, reconciliation, paper/live order
submission, automatic exits, holdings monitoring, Ajaib scraping, or inferring
the user's portfolio. FMP remains discovery; SEC/issuer evidence remains the
primary evidence source.

## 3. Relevant existing modules and specifications

Read [AGENTS.md](../../AGENTS.md), [PLANS.md](../../PLANS.md), the active
[scope revision](001-mvp-scope-revision.md), [TRADING_POLICY.md](../TRADING_POLICY.md),
[ARCHITECTURE.md](../ARCHITECTURE.md), [ROADMAP.md](../ROADMAP.md), and archived
[IBKR architecture](../archive/ibkr-design/ARCHITECTURE.md).

Use `market/ajaib_hints.py`, `providers/twelve_data.py`, `providers/sec_edgar.py`,
`research.py`, and existing SQLite provenance/cache patterns as references. The
uncommitted TradingAgents batch script remains non-authoritative supplementary
research and is not part of the IBKR integration.

## 4. Proposed design and alternatives considered

Create a `DislocationInvestigation` with a fixed UTC cutoff. Request a narrow
pre-event/post-event IBKR bar window and, only when entitled, one quote. Persist
instrument identity, exchange/currency, interval, regular-hours policy, source
time, retrieval time, session health, and response hash. Pure code finds the
decline start, low, and bounded recovery, compares volume to a pre-event
baseline, and joins the timeline to dated primary evidence.

Alternatives: Twelve Data alone is insufficient for the prior BRZE timing;
FMP remains discovery but has prior entitlement limits; reviving IBKR execution
is rejected because the recommendation-only MVP needs no execution. Manual chart
inspection is rejected because it is not reproducible or auditable.

## 5. Data-model or API changes

Add offline typed contracts: `MarketObservation`, `DislocationWindow`,
`DislocationInvestigation`, and `MarketDataHealth`. They include UTC times,
OHLCV/quote facts, calculation inputs, evidence references, uncertainty and
provenance, while excluding account/order/position/cash data.

Define a `MarketDataProvider` for approved bars and a single quote. Keep
`IbkrReadOnlyMarketDataProvider` behind that boundary. SQLite migrations and
CLI commands wait until fixture contracts and provider feasibility pass.

## 6. Safety invariants and failure behavior

- The adapter may expose only session health, contract qualification, bars and
  quote data; account, portfolio, order and execution calls are unavailable.
- Unentitled, delayed, ambiguous, stale, incomplete or failed data returns a
  structured block; it never becomes a price or recommendation.
- Conclusions name the exact window and distinguish documented events from
  inferred explanations.
- Models cannot set size, entry, stop, target or action, or override a blocked
  evidence/risk gate.
- Never persist credentials, account identifiers, private portfolio data or raw
  production logs.

## 7. Ordered implementation steps

- [ ] I01: Confirm TWS API, IB Gateway, or Client Portal access; market-data
  entitlement; and whether the available feed is real-time or delayed. Record no
  secrets.
- [ ] I02: Update active architecture/roadmap/scope documentation to distinguish
  this read-only experiment from deferred IBKR execution.
- [ ] I03: Add offline investigation contracts and validation tests for UTC,
  non-finite data, unknown fields, invalid windows and missing provenance.
- [ ] I04: Implement pure decline-window and volume-baseline calculations from
  fixture bars, including no-data and cutoff boundaries.
- [ ] I05: Test earnings-guidance selloff, sector selloff, data gap, stale quote,
  delayed entitlement, conflicting event times and post-cutoff recovery.
- [ ] I06: Verify official IBKR API documentation, select one dependency and
  document/lock it; do not connect.
- [ ] I07: Implement a deny-by-default read-only adapter and tests proving
  account/order method names are unavailable.
- [ ] I08: Add connection/request/disconnect timeouts and structured health
  blocks for entitlement, delay and session failures.
- [ ] I09: With explicit local configuration and approval, smoke-test BRZE
  session health and contract qualification only.
- [ ] I10: With explicit approval, retrieve BRZE's approved investigation window
  and compare it with its 2026-09-08 8-K and Exhibit 99.1 timeline.
- [ ] I11: Build BRZE's cited evidence packet, apply `evaluate_business_gate`,
  and formally record its outcome. $50 is a sizing input only after S19/D04.
- [ ] I12: Run required checks and commit each checked step with code, tests and
  resume notes.

## 8. Test and validation plan

Run `uv sync --locked`, Ruff format/check, mypy, pytest and scenarios. Mock the
IBKR boundary to prove it cannot invoke account or order operations. Verify UTC
cutoffs, bars/volume calculations, stale-data blocks and entitlement/session
failures. A real smoke test must log only sanitized read-only request names.

## 9. Rollback or recovery approach

This plan creates no remote state. Revert each implementation step independently.
If the selected client exposes account/order capabilities, remove the adapter
before connecting. On a stalled session, disconnect, record health failure and
retain no partial recommendation. Preserve existing evidence and SQLite data.

## 10. Open decisions requiring user approval

- **D11:** exact IBKR access method, data subscription/entitlement and permitted
  use; no credentials in source or plan.
- **D12:** pre/post-event duration, bar interval, regular/extended-hours policy,
  and sudden-selloff definition.
- **D13:** minimum primary evidence required to classify a guidance selloff versus
  a sector/general move.
- **D14:** whether $50 is maximum notional, fractional-share support, and maximum
  loss limit before deterministic S19 sizing.
- **D15:** whether to commit the batch TradingAgents script as a non-authoritative
  developer tool.
