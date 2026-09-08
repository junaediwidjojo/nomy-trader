# Data model — recommendation MVP

Changed 2026-09-08. Original broker entities and transitions are preserved in
[historical data model](archive/ibkr-design/DATA_MODEL.md), deferred from MVP.

SQLite uses foreign keys, WAL, transactions, migrations, UTC and backups.
It is authoritative for recorded evidence, recommendations and notification
attempts only. There is no source of truth for user holdings or executions here.

- Event: symbol, detection/market time, computed filters, source and dedup key.
- Evidence: immutable source/version, publication, availability and retrieval
  times, content hash, licensed reference/content and event relationship.
- Decision: REJECT, WAIT or PROPOSE_BUY, validated evidence references, rationale,
  uncertainty, confidence and strategy/model/prompt versions. Invalid outputs
  produce validation records, not repaired recommendations.
- TradePlan: all applicable policy fields including entry, valuation scenarios,
  targets, advisory stop/durations/exit policy, thesis, assumptions, invalidations,
  evidence and uncertainty. No fabricated filled price or quantity.
- SizingInputs/PolicyVersion: immutable approved capital/risk assumptions and
  as-of/source metadata; deterministic suggested quantity/notional and formula.
- Recommendation: immutable full serialized TradePlan and schema/policy version,
  plan/event identity, quote time and creation time. Revisions create new rows.
- NotificationAttempt/outbox: unique recommendation/destination intent, status,
  attempt timestamps, confirmed sent time, provider message ID and sanitized
  errors. PENDING -> SENDING -> SENT/FAILED/UNKNOWN. Retain every attempt;
  UNKNOWN after ambiguous dispatch is not automatically resent. SENT is delivery
  acknowledgement, not read confirmation or execution.
- ScanRun, cached market snapshot and QuotaReservation: provenance and persistent
  account-wide FMP budget usage. Restart cannot restore spent calls.
- SystemState: market-data, quota, AI/evidence and notification health; no broker
  session, cash, portfolio state or paper/live switch.

Commit recommendation and outbox in one transaction before sending. Keep full
sent recommendation data for manual export. Do not infer holdings or exposure
from sent messages. Order, Fill, PositionSnapshot, PositionReview, reconciliation
and active position lifecycle are removed from the active MVP model; prior
partial implementation must be reviewed after plan approval.

## Implemented domain foundation

`domain.models` supplies immutable Event/Evidence/Decision/TradePlan/thesis
revision, SizingInputs/SuggestedSize, Recommendation, NotificationAttempt and
explicit policy/health contracts. `validate_recommendation` checks context,
chronology, arithmetic and caps; it does not calculate final size or send.
Duration fields explicitly use calendar days; actual duration values are unset.
Portfolio applicability is explicitly `unavailable`, following user decision.
Notification status has no trade-state semantics. Current recommendation
validation requires evidence retrieval before analysis; historical context
validation may accept later archival retrieval with earlier proven availability.
Persistence/append-only database enforcement remains the next milestone.
