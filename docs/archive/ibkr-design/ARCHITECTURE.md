# Architecture

## Style

One Python repository and one primary long-running process: a modular monolith.
Deploy on one Linux machine with process supervision. Avoid distributed-system
components until measured scale or reliability requirements demand them.

## Technology baseline

- Python 3.12+ and `uv`.
- Pydantic for external inputs and model outputs.
- pandas initially for research features.
- SQLite with SQLAlchemy and Alembic.
- APScheduler plus an exchange calendar.
- Official IBKR TWS API behind an adapter; paper account only.
- OpenAI Responses API function calling behind a model adapter.
- `httpx` for evidence providers.
- Structured standard logging and pytest-based verification.
- Optional Telegram or email notifications.

Dependencies and exact versions are implementation decisions to lock and
document during the relevant milestone.

## Runtime flow

```text
scheduler
  -> IBKR/candidate scanner
  -> deterministic candidate filters
  -> evidence tools
  -> bounded event analyst
  -> deterministic valuation calculator
  -> deterministic risk engine
  -> idempotent IBKR paper broker adapter
  -> journal and notification
```

## Scheduling

- Position monitor: approximately every minute; deterministic only.
- Candidate scan: approximately every five minutes during configured sessions.
- AI analysis: once per distinct event, then only upon material new evidence.
- Thesis review: event-triggered plus at most one scheduled daily review.
- End-of-day reconciliation and report.

Intervals remain configurable and must respect API limits. Market sessions must
come from an exchange calendar, not hand-coded local times.

## Tool boundary

Initial model tools are typed in-process functions, not MCP services:

- `get_price_event`
- `get_related_news`
- `get_primary_disclosures`
- `get_financial_snapshot`
- `compare_market_and_peers`
- `calculate_scenario_value`
- `get_portfolio_exposure`

Tools return bounded structured data and immutable evidence references. The
model has no shell, database mutation, credential, or raw broker-order tool.

## Failure behavior

- Stale or missing market data: reject candidate and alert.
- Evidence unavailable: classify uncertainty; do not manufacture a cause.
- Invalid model output: reject and record validation failure.
- Model outage: continue deterministic monitoring and broker protection.
- IBKR disconnect: freeze new orders; attempt bounded reconnect and alert.
- Ambiguous submission acknowledgement: reconcile before retrying.
- Broker/database mismatch: freeze new entries and require reconciliation.
- Missing protective order: repair if safe or alert and freeze entries.

## Operational boundary

IB Gateway or TWS is a separate local dependency. Authentication cannot be
assumed indefinitely unattended. Session health is an explicit monitored state.

## Security

- Secrets come from environment or an OS secret mechanism, never the repo.
- Sanitize logs and portfolio demonstrations.
- Validate all tool arguments and outputs.
- Separate retrieved content from developer/system instructions.
- Use least-privilege paper credentials during development.

