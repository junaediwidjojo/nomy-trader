# Generic price-signal workflow ExecPlan

Status: approved for implementation 2026-09-09. This plan makes BRZE a fixture,
not a special case. It supersedes the immediate-analysis ordering in S17c only
for the generic price-signal path; broker execution remains excluded.

## 1. Goal and user-visible outcome

For every eligible Ajaib decline, produce a reproducible research result:
event explanation, business-risk status, bear/base/bull fair-value range, entry
zone, maximum entry ceiling, fresh-market status, TradingAgents challenge, and
one final outcome: `REJECT`, `WATCH`, or `MANUAL_BUY_CANDIDATE`.

The system persists the facts and assumptions needed to reproduce the result.
Telegram delivery is deferred until the signal core is complete.

## 2. Scope and explicit non-goals

Scope: generic offline contracts, deterministic valuation/entry computation,
evidence and market-confirmation gates, a non-authoritative TradingAgents review
adapter boundary, CLI fixture workflow, and failure-path tests.

Non-goals: broker access, orders, positions, fills, automatic exits, portfolio
tracking, price prediction, automated news scraping without an approved provider,
and Telegram delivery. A model cannot set final price, size, stop, target or
outcome.

## 3. Relevant existing modules and specifications

Use `market.ajaib_hints` for discovery, `research.py` and `providers.sec_edgar`
for evidence patterns, domain valuation/plan contracts, Twelve Data quote
contracts, SQLite journal patterns, and plans 001–003. `scripts/` and `var/`
remain local, uncommitted tooling/output. TradingAgents is an external,
supplementary source and has a documented Yahoo Finance timeout blocker.

## 4. Proposed design and alternatives considered

Pipeline: `DiscoveryHint -> EvidencePacket -> BusinessGate -> ValuationInputs ->
DeterministicPriceSignal -> FreshMarketGate -> TradingAgentsReview ->
SignalOutcome`. Every stage returns facts or a structured block; later stages
never repair missing earlier-stage facts.

Valuation uses explicit low/base/high fair-value scenarios and an approved margin
of safety. The entry ceiling is `fair_value.low * (1 - margin_of_safety)`;
entry zone is a bounded range below that ceiling. Fresh-market confirmation only
confirms quoted state and approved technical conditions. TradingAgents sees
sanitized supplied facts and may challenge the thesis, but cannot determine the
price or outcome.

Alternatives rejected: letting TradingAgents supply a precise entry price;
hard-coding BRZE levels; treating an Ajaib snapshot as fresh executable data;
and using a single news article as a sufficient explanation.

## 5. Data-model or API changes

Add frozen contracts for `ValuationInputs`, `PriceSignal`, `MarketConfirmation`,
`TradingAgentsReview`, and `SignalOutcome`. Price signals include Decimal values,
formula/version, scenario assumptions, evidence IDs, quoted-at UTC, and explicit
blocks. Reviews include source/report hash, report time, cited facts and a
challenge status, never price/size/action fields.

Add pure functions for fair value, entry ceiling, entry-zone bounds, market
confirmation and final composition. Add a local JSON-fixture CLI; SQLite
persistence/API adapters wait until the pure core passes.

## 6. Safety invariants and failure behavior

- Unknown/stale evidence, market data, valuation inputs or model review blocks
  promotion; no fallback price is invented.
- Fair values, entry ceilings and zones use Decimal and explicit assumptions.
- Entry ceiling is deterministic; model text cannot override it.
- TradingAgents timeout, malformed review, unsupported citation or unavailable
  provider yields an explicit unavailable/challenge block, never a silent pass.
- Ajaib data is a discovery hint. Fresh market confirmation must name provider,
  timestamp and venue limitation.
- The composed result never claims execution, holdings, performance or a
  guaranteed return.

## 7. Ordered implementation steps

- [ ] P01: Define fixture cases for temporary event, structural risk, no event,
  stale market data, positive/negative TradingAgents challenge and malformed
  review.
- [x] P02: Add valuation input and deterministic price-signal contracts; reject
  nonfinite/negative/inverted/missing scenario data and invalid margin safety.
- [x] P03: Implement fair-value, entry-ceiling and entry-zone calculations with
  Decimal-only arithmetic and formula/version provenance.
- [x] P04: Add market-confirmation contract and pure freshness/technical gate.
- [x] P05: Add a strict TradingAgents review contract that permits only
  evidence-linked challenge/support commentary, not price/action/size fields.
- [x] P06: Compose deterministic gates and review into `REJECT`, `WATCH`, or
  `MANUAL_BUY_CANDIDATE`; test every block and conflict path.
- [x] P07: Add JSON fixture CLI output showing every stage, assumption, price
  signal and limitation without provider calls.
- [ ] P08: Integrate approved SEC document/evidence retrieval and a fresh market
  provider, preserving timestamps and source revisions.
- [ ] P09: Add a timeout-bounded TradingAgents adapter that receives only
  curated facts and records a report hash; never invoke its raw graph in the
  recommendation path until its Yahoo fallback is fixed.
- [ ] P10: Persist completed signals, add delivery later, and run full quality
  checks after each completed step.

## 8. Test and validation plan

Run locked sync, Ruff format/check, mypy, pytest and scenarios. Test formula
boundaries, Decimal precision, missing assumptions, stale quotes, evidence
absence, malformed/unavailable reviews, conflicting review vs valuation, and
that no model field can change a deterministic entry ceiling. Fixtures need no
credentials or network.

## 9. Rollback or recovery approach

Pure contracts/functions and fixtures are independently revertible. Do not alter
existing recommendation/evidence records. Provider/review failures retain the
block result and do not queue delivery. Preserve local Ajaib snapshots and
external TradingAgents output outside tracked source.

## 10. Open decisions requiring user approval

- **P-D01:** valuation methodology for growth, unprofitable, financial and
  asset-heavy companies; one formula cannot safely cover every sector.
- **P-D02:** margin-of-safety range and entry-zone width.
- **P-D03:** fresh-market age, volume/trend confirmation rules and accepted
  providers.
- **P-D04:** minimum evidence standard for each event type and the approved news
  provider.
- **P-D05:** whether a failed/unavailable TradingAgents challenge blocks a signal
  or leaves a deterministic `WATCH` outcome.
