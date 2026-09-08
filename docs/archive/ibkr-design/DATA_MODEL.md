# Data model

SQLite is suitable for the initial single-process workload. Enable foreign
keys, WAL mode, transactions, UTC timestamps, and backups.

## Authority

| Domain | Authority |
| --- | --- |
| Cash, positions, orders, fills | IBKR |
| Thesis, evidence, valuation, exit plan | SQLite |

## Entities

### Event

Represents one detected abnormal decline. Fields include symbol, detection and
market timestamps, return, standardized movement, volume context, scanner
origin, status, and deduplication key.

### Evidence

Immutable source snapshot metadata: type, source URI/reference, publisher,
publication time, retrieval time, content hash, event relationship, and whether
it is a primary source. Preserve enough point-in-time content or licensed
reference information to reproduce analysis legally.

### Decision

Every model or deterministic conclusion, including REJECT, WAIT, PROPOSE_BUY,
HOLD, REDUCE, and EXIT. Store structured output, input/evidence references,
model and prompt versions, confidence, timestamp, and validation result.

### TradePlan

One approved plan attached to an event: valuation scenarios, entry ceiling,
target range, stop, duration, thesis, assumptions, invalidations, risk budget,
and state. A broker position must have exactly one active plan.

### ThesisVersion

Append-only revisions to a trade plan's thesis. Never overwrite prior versions.
Record the triggering evidence and changed assumptions.

### PositionReview

Scheduled or event-triggered review containing the current broker snapshot,
active thesis version, new evidence, recommendation, and risk decision.

### Order

Client-generated idempotency key, broker order ID, intent, side, quantity,
order type, limit/stop fields, state, timestamps, and related plan.

### Fill

Immutable broker execution: execution ID, order ID, symbol, side, quantity,
price, commissions when available, and timestamp.

### PositionSnapshot

Periodic broker-authoritative quantity, cost basis, market price, open orders,
and unrealized result used for reconciliation and audit.

### SystemState

Broker session, data freshness, risk gates, scheduler heartbeat, last successful
reconciliation, and global paper/live mode. Initial mode is always paper.

## State transitions

Order: PROPOSED -> SUBMITTED -> ACKNOWLEDGED -> PARTIALLY_FILLED -> FILLED,
with CANCELLED, REJECTED, and UNKNOWN terminal/recovery branches.

Trade plan: DRAFT -> APPROVED -> ENTRY_PENDING -> OPEN -> REDUCING -> CLOSED,
with REJECTED, EXPIRED, and RECONCILIATION_HOLD branches.

No state transition may rely solely on an LLM statement. Broker-related states
require broker evidence.

## Reconciliation invariants

- Broker position without active plan: freeze automation and alert.
- Active plan without broker position: reconcile pending/cancelled/filled order
  history before closing or repairing state.
- Quantity mismatch: freeze affected automation and reconcile fills.
- Unknown submission result: never blindly resubmit.
- Closed plan retains all decisions, thesis versions, orders, and fills.

