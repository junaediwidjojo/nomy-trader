# Evaluation specification

## Central question

Does AI-assisted event interpretation improve risk-adjusted, after-cost outcomes
over a deterministic abnormal-decline baseline on genuinely point-in-time data?

## Compared systems

1. Deterministic abnormal-decline baseline.
2. Baseline plus simple event exclusions.
3. Baseline plus AI event classification.
4. Baseline plus AI classification and scenario-thesis review.
5. Buy-and-hold market benchmark.
6. Appropriate sector benchmark.

## Data integrity

- Use publication timestamps, not later ingestion timestamps alone.
- Prevent revised filings, later headlines, future prices, and future index
  membership from entering historical decisions.
- Model realistic decision delay after detection and evidence retrieval.
- Account for delisted companies and rejected candidates where possible.
- Version datasets, prompts, models, code, and strategy parameters.

Historical news licensing and faithful snapshots are an explicit research risk;
do not claim a valid event backtest until resolved.

## Trading metrics

- Net return after commissions, spread, FX, and modeled slippage.
- Maximum drawdown.
- Sharpe and Sortino ratios with stated conventions.
- Win rate, payoff ratio, and profit factor.
- Turnover, exposure, concentration, and holding duration.
- Performance by event category and market regime.
- Tail outcomes and sensitivity to worse execution.

## AI metrics

- Event-cause identification accuracy.
- Event-classification precision/recall by category.
- Confidence calibration.
- Unsupported-claim and citation/error rates.
- Schema-validation failure rate.
- Decision stability under irrelevant context changes.
- Incremental benefit over the deterministic baseline.
- Cost and latency per analyzed event.

## Scenario tests

Build deterministic fixtures for:

- Temporary operational issue followed by recovery.
- Correct repricing after permanent guidance reduction.
- Fraud or governance allegation.
- Sector-wide panic.
- No identifiable news.
- Conflicting sources.
- Late or revised evidence.
- Stale price data.
- Partial fill and duplicate acknowledgement.
- Model outage while a position is open.
- Broker/database mismatch.

## Promotion gates

No future live proposal until, at minimum:

- Research methodology passes leakage review.
- After-cost out-of-sample results are reported honestly.
- Paper/shadow operation covers multiple months and market conditions.
- Reconciliation and idempotency failures are resolved.
- Drawdown and operational limits are approved.
- The AI version demonstrates measured benefit over the simpler baseline.
- A separate live-trading ADR, threat model, runbook, and explicit approval exist.

Passing gates does not imply future profit.

