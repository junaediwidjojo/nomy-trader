# Ajaib priority-ranking ExecPlan

Status: approved and implemented 2026-09-10. This plan adds an explainable review order after
the existing deterministic decline filter. It does not change eligibility or
make a trade recommendation.

## 1. Goal and user-visible outcome

Turn the current flat set of Ajaib decline hints into a reproducible ranked
queue. Each candidate will show its rank, numeric score, score components and
the snapshot revision that produced it, so the user can see which names should
receive primary-evidence research first.

## 2. Scope and explicit non-goals

Scope: pure priority-score contracts and calculations, score explanation in the
`ajaib-hints` CLI output, persisted scan payload, fixture tests and an explicit
policy version.

Non-goals: changing the existing price, market-cap, one-day or one-week
eligibility rules; calculating fair value; assigning an entry price; measuring
liquidity; running TradingAgents; treating a high score as business quality or
a buy decision.

## 3. Relevant existing modules and specifications

Use `market.ajaib_hints.AjaibReversalHint` and `run_reversal_hint_scan`, the
immutable `scan_runs` payload, the current Ajaib filters (price above $5,
market cap above $100M, one-day decline at least 1%, one-week decline at least
3%), and the generic workflow in ExecPlan 004. The latest snapshot shows that
sorting only by one-day loss is insufficient when 199 candidates pass.

## 4. Proposed design and alternatives considered

Create a versioned `PriorityPolicy` and a `RankedAjaibHint`. The score has
separate disclosed components rather than a hidden formula:

`severity = max(0, -one_day_percent) * one_day_weight`

`raw_reversal_context = max(0, one_month_percent - one_month_floor) * one_month_weight`

`reversal_context = min(raw_reversal_context, severity * one_month_context_cap_fraction)`

`priority_score = severity + reversal_context`

The score is descending; symbol is the deterministic tie-breaker. A missing
one-month value receives no reversal-context points and remains eligible.
This ranks acute declines with less prolonged one-month weakness ahead of names
already in extended downtrends. The cap ensures a small daily move after a
large monthly rise cannot outrank a larger sudden decline. It is a
research-order heuristic, not proof of an overreaction.

Alternatives rejected: daily-drop-only ordering because it produced an
unexplained 199-name queue; a model-generated rank because it cannot be
reproduced; and excluding negative one-month candidates because that silently
changes discovery eligibility.

## 5. Data-model or API changes

Add immutable `PriorityPolicy`, `PriorityBreakdown` and `RankedAjaibHint`
contracts. Add `rank_reversal_hints(candidates, policy)` as a pure function.
`AjaibReversalHintScan` will carry the policy, ranked candidates and its score
breakdown; the existing candidate fields remain visible for compatibility.
Add an `--priority-policy` JSON option only after the default policy is
approved; no policy values are read from an untracked environment file.

## 6. Safety invariants and failure behavior

- Ranking begins only after the existing eligibility filter; it cannot restore
  rejected stocks.
- Every output includes policy version, inputs and score components.
- Missing or nonfinite values never receive invented points.
- A priority score cannot enter a valuation, plan, sizing or final outcome.
- Invalid weights, negative score thresholds, duplicate symbols or missing
  policy version fail explicitly.

## 7. Ordered implementation steps

- [x] R01: Add ranking fixtures covering severe short-term decline, prolonged
  downtrend, positive one-month context, missing one-month data and score ties.
- [x] R02: Add validated versioned policy, breakdown and ranked-hint contracts.
- [x] R03: Implement pure deterministic score calculation and tie-breaking.
- [x] R04: Integrate ranked candidates and policy provenance into the saved
  Ajaib scan payload without changing the base filter.
- [x] R05: Print compact rank, score and components in `ajaib-hints`; add an
  optional top-N limit so normal logs remain readable.
- [x] R06: Run formatting, linting, type checks, all tests and scenarios; mark
  completed boxes and commit each completed step with code.

## 8. Test and validation plan

Test exact Decimal scores, ordering, alphabetical ties, missing one-month
values, invalid policies and proof that an existing rejected hint remains
rejected. Test scan persistence/restart and CLI top-N output. Run `uv sync
--locked`, Ruff format/check, mypy, pytest and scenarios without credentials.

## 9. Rollback or recovery approach

The ranking is an added scan-payload field and pure function. Revert its source
and migration-free payload behavior to restore the prior daily-drop ordering;
existing raw Ajaib snapshots and older scans remain intact. It creates no
external state.

## 10. Open decisions requiring user approval

- **R-D01:** approved 2026-09-10: `one_day_weight = 1.0`,
  `one_month_weight = 0.25`, `one_month_floor = -10.0`, and
  `one_month_context_cap_fraction = 0.25`.
  A stock with a sharper daily fall receives priority, while
  a stock already down more than 10% for the month receives no context bonus;
  the one-month bonus cannot exceed 25% of daily severity. The cap was added
  during R05 verification because the uncapped formula incorrectly ranked a
  modest daily fall after a strong monthly rise above BRZE.
- **R-D02:** approved 2026-09-10: default CLI output is top 20, with the full
  ranked list retained in SQLite.
