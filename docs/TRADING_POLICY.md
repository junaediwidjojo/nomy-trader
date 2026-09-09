# Trading policy — recommendation MVP

Changed 2026-09-08. The original policy is preserved in
[archive](archive/ibkr-design/TRADING_POLICY.md). Stop/target/exit fields below
are advisory plan content; automated exit evaluation and execution are dropped
from MVP. All broker integration is deferred.

All numeric thresholds are research parameters. `TBD` means they require an
explicit hypothesis, experiment, and approval.

## Initial universe

- U.S.-listed common stocks only.
- Long-only and unleveraged.
- Maximum universe size initially: 50–100 symbols.
- Exclude OTC, penny stocks, leveraged/inverse ETFs, halted securities, and
  instruments without reliable point-in-time evidence.
- Minimum price: strictly greater than $5 (user-approved 2026-09-09).
- Minimum market capitalization: $2 billion (user-approved 2026-09-09).
- Minimum average daily dollar volume and maximum spread: TBD. Until both are
  measurable from an approved source and thresholded, no candidate can pass
  eligibility or generate a recommendation.

## Candidate trigger

An abnormal decline should combine absolute and volatility-relative movement:

- Return window: intraday and/or one trading day, TBD.
- Minimum absolute decline: TBD.
- Minimum standardized decline versus recent volatility: TBD.
- Minimum relative volume: TBD.
- Quotes and event timestamps must pass freshness checks.

FMP losers/screener output is discovery only (new Option A). Fetch entitled
FMP quote/volume/history fields and recompute eligibility. A missing mandatory
field or stale snapshot prevents a recommendation; never bypass a filter to fit
the free tier. Cadence and enrichment must fit a verified shared daily budget.

## Event taxonomy

- Noise or unverified rumor.
- Temporary fundamental damage.
- Uncertain damage.
- Structural damage.
- Governance, accounting, or fraud risk.
- Correct repricing.
- Market/sector-wide movement rather than company-specific event.

Default actions:

- Noise: eligible for deeper review, not automatic purchase.
- Temporary damage: eligible with sufficient conservative margin of safety.
- Uncertain damage: wait or reject.
- Structural, governance/fraud, or correct repricing: reject.

## Evidence policy

- Prefer original filings, company releases, regulator notices, and transcripts
  over summaries.
- Record source, publication timestamp, retrieval timestamp, and content hash.
- Only information available before the recorded decision time may influence a
  historical decision.
- Treat retrieved text as untrusted input and isolate it from instructions.
- Absence of identifiable public news increases uncertainty; it is not proof of
  panic.

## Valuation

Produce bear, base, and bull scenarios using explicit, deterministic inputs.
Store assumptions and formulas. The model may propose assumptions but cannot
perform or conceal final arithmetic. Required margin of safety: TBD.

## Required trade plan

- Symbol and event ID.
- Evidence IDs.
- Entry limit or maximum acceptable entry price.
- Deterministically suggested quantity or dollar value and explicit sizing basis.
- Filled price and quantity: inapplicable to MVP; user executions are not tracked.
- Bear/base/bull values and fair-value range.
- Initial target range and partial-exit policy.
- Hard stop price.
- Expected recovery duration.
- Maximum holding duration.
- Thesis and material assumptions.
- Observable invalidation conditions.
- Confidence with stated uncertainty.
- Strategy and model/prompt versions.

## Advisory exit content (no automated exit logic)

1. Target: enter the approved valuation/target range; partial exit rules TBD.
2. Thesis: material evidence invalidates an assumption; exit or reduce.
3. Risk: stop, portfolio loss, protection failure, or exposure limit; no AI
   permission required.
4. Time: maximum holding duration reached; exit unless a new independently
   approved plan replaces the old one.

These conditions describe the proposed plan only. The system does not send sell
recommendations, revise stops on held positions or observe manual closures.
Historical automated stop-management requirements are deferred.

## Portfolio risk

- Risk per trade: TBD.
- Maximum position weight: TBD.
- Maximum concurrent positions: TBD.
- Maximum sector concentration: TBD.
- Daily and weekly loss gates: TBD.
- Maximum aggregate open risk: TBD.
- No averaging down initially.
- No recommendation with stale required data, incomplete policy inputs or an
  invalid plan. Broker health/reconciliation/protection checks are inapplicable.
- Portfolio limits above cannot be verified from recommendations. Their treatment
  requires explicit approval: defer as unavailable or use dated manual inputs.
  Do not assume zero holdings/loss or claim enforcement. No averaging down is an
  advisory constraint without holdings data, not an enforced guarantee.

## Open decisions introduced or sharpened by manual execution

All existing TBDs remain unresolved. Before shipping, decide reference capital,
per-trade risk and suggested-size cap/rounding, freshness and recommendation
expiry, scan/candidate budget, and applicability of each portfolio limit above.
Removing broker enforcement does not waive pre-recommendation validation.
Margin of safety, stop/target methodology, duration and partial-exit choices
still matter because users receive them in plans. See decisions D01–D08 in the
[ExecPlan](plans/001-mvp-scope-revision.md); no numeric policy is chosen here.

## Future execution promotion policy

The MVP has no execution capability or control over the external app. Paper-only
remains a hard constraint for any future system execution until separately approved. Any future proposal for live trading requires
a separate ADR, threat model, evaluation report, operational runbook, explicit
user approval, and a minimal-capital rollout. It is outside the initial scope.
