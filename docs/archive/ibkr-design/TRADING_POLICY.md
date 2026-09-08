# Trading policy

All numeric thresholds are research parameters. `TBD` means they require an
explicit hypothesis, experiment, and approval.

## Initial universe

- U.S.-listed common stocks only.
- Long-only and unleveraged.
- Maximum universe size initially: 50–100 symbols.
- Exclude OTC, penny stocks, leveraged/inverse ETFs, halted securities, and
  instruments without reliable point-in-time evidence.
- Minimum price, market capitalization, dollar volume, and maximum spread: TBD.

## Candidate trigger

An abnormal decline should combine absolute and volatility-relative movement:

- Return window: intraday and/or one trading day, TBD.
- Minimum absolute decline: TBD.
- Minimum standardized decline versus recent volatility: TBD.
- Minimum relative volume: TBD.
- Quotes and event timestamps must pass freshness checks.

IBKR scanner output is discovery only. Fetch independent quote/bar fields and
recompute eligibility.

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
- Filled price and quantity after execution.
- Bear/base/bull values and fair-value range.
- Initial target range and partial-exit policy.
- Hard stop price.
- Expected recovery duration.
- Maximum holding duration.
- Thesis and material assumptions.
- Observable invalidation conditions.
- Confidence with stated uncertainty.
- Strategy and model/prompt versions.

## Exits

1. Target: enter the approved valuation/target range; partial exit rules TBD.
2. Thesis: material evidence invalidates an assumption; exit or reduce.
3. Risk: stop, portfolio loss, protection failure, or exposure limit; no AI
   permission required.
4. Time: maximum holding duration reached; exit unless a new independently
   approved plan replaces the old one.

Stops may be raised but not lowered by AI. Manual emergency closure is always
permitted and must be recorded.

## Portfolio risk

- Risk per trade: TBD.
- Maximum position weight: TBD.
- Maximum concurrent positions: TBD.
- Maximum sector concentration: TBD.
- Daily and weekly loss gates: TBD.
- Maximum aggregate open risk: TBD.
- No averaging down initially.
- No new entries during reconciliation, stale-data, broker-session, or
  protective-order failures.

## Promotion policy

Paper-only is a hard constraint. Any future proposal for live trading requires
a separate ADR, threat model, evaluation report, operational runbook, explicit
user approval, and a minimal-capital rollout. It is outside the initial scope.

