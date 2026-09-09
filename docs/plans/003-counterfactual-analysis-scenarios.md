# Counterfactual analysis scenario ExecPlan

Status: proposed 2026-09-09. Implement only after approval. This plan adds an
offline learning tool; it does not create a market-data provider, recommendation,
notification, price target, order or backtest performance claim.

## 1. Goal and user-visible outcome

Let the user ask a transparent “what if?” question, such as “what changes if
BRZE is $12?”, and receive a scenario report showing which deterministic gates,
valuation assumptions and supplementary TradingAgents observations would change.
Every result identifies the supplied synthetic facts and ends as `SCENARIO_ONLY`,
never `BUY`, `SELL`, `MANUAL_BUY_CANDIDATE` or an executable price.

## 2. Scope and explicit non-goals

Scope: offline scenarios with explicitly supplied symbol, UTC as-of time,
hypothetical price, optional volume and declared unchanged evidence/fundamentals.
The output compares a base observation against the scenario and records missing
facts.

Non-goals: forecasting whether a price will occur, altering historical records,
querying live providers, claiming a valuation target, sizing, stop calculation,
backtesting, automated TradingAgents execution, or sending Telegram messages.

## 3. Relevant existing modules and specifications

Read AGENTS.md, PLANS.md, `research.py`, domain validation, the active scope
revision plan S17/S18/S19, and the proposed read-only IBKR plan. Reuse immutable
contract conventions and existing fixture/scenario infrastructure. TradingAgents
remains external and non-authoritative.

## 4. Proposed design and alternatives considered

Add a pure `CounterfactualMarketObservation` that requires a base observation
reference and marks all overwritten facts synthetic. A scenario runner feeds
only deterministic calculations and, optionally, a pre-recorded TradingAgents
report with a visible warning that it was not generated at the hypothetical
price. The report separates: observed facts, synthetic facts, unchanged facts,
and blocked conclusions.

Do not call TradingAgents with a made-up price by changing its tool output: that
would make its prose appear to be a real market-data result. A later, separate
approved test harness may inject a fully synthetic data provider, but only after
all synthetic provenance is preserved.

## 5. Data-model or API changes

Add immutable `ScenarioInput`, `CounterfactualMarketObservation` and
`ScenarioResult` contracts. Require Decimal price, UTC as-of time, scenario ID,
base-observation ID, assumption list, source classification and explicit
`SCENARIO_ONLY` status. Reject naive times, unknown fields, non-finite values,
negative prices, missing base references and attempts to attach a scenario to a
recommendation/notification.

Expose a local CLI command accepting a JSON scenario fixture. It writes no
SQLite state by default and prints a machine-readable result.

## 6. Safety invariants and failure behavior

- Synthetic price data is never mixed with observed market data.
- A scenario cannot create, revise or validate a TradePlan or recommendation.
- Models receive no authority and cannot supply an assumed price, entry, stop,
  target or size.
- Missing base facts, stale base observation or incomplete assumptions blocks
  directional interpretation and reports the missing data.
- Output labels every conclusion `SCENARIO_ONLY` and names the hypothetical
  price in its first line.

## 7. Ordered implementation steps

- [ ] C01: Define the approved BRZE $12 scenario inputs, base observation and
  unchanged-fundamentals assumption in a fixture; no provider request.
- [ ] C02: Add typed scenario contracts and validation tests.
- [ ] C03: Implement pure base-versus-scenario percentage and valuation-input
  comparison; do not calculate an entry or recommended allocation.
- [ ] C04: Add a CLI JSON-fixture runner with prominent synthetic labeling.
- [ ] C05: Test malformed values, stale/missing base, unknown fields, attempted
  recommendation linkage and accidental observed/synthetic mixing.
- [ ] C06: Run the BRZE $12 fixture, publish its `SCENARIO_ONLY` output and
  document which real-world evidence would be needed to convert it into research.
- [ ] C07: Run formatting, linting, types, tests and scenarios; commit the
  checked plan step with code and tests.

## 8. Test and validation plan

Run the repository's locked sync, Ruff format/check, mypy, pytest and scenario
command. Assert that every printed scenario includes `SCENARIO_ONLY`, its
assumptions and the supplied price; assert it cannot instantiate a recommendation
or notification. Use only fixtures, without credentials or network access.

## 9. Rollback or recovery approach

The feature is isolated pure code and fixtures. Revert its package/configuration
files without touching observed evidence, SQLite recommendations, local Ajaib
snapshots or external TradingAgents reports. No remote state exists.

## 10. Open decisions requiring user approval

- **C-D01:** approve $12 as an educational BRZE scenario price and specify the
  base observation to compare against.
- **C-D02:** approve which variables stay unchanged: only fundamentals/evidence,
  or also volume, market index and peer behavior. Missing variables remain
  unknown rather than assumed.
- **C-D03:** approve whether scenarios may use a fully synthetic TradingAgents
  provider in a later experiment. The initial plan deliberately excludes it.
