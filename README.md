# nomy-trader

Educational, AI-assisted buy-side recommendations: FMP candidate discovery,
deterministic eligibility and advisory sizing, complete trade plans logged to
SQLite, and Telegram notifications. The user executes independently elsewhere.
No broker integration, position tracking, reconciliation or automated exits.
Stop and target fields are advisory; profitability is not assumed.

## Current status

The [ExecPlan](docs/plans/001-mvp-scope-revision.md) is approved. Milestone 1
provides immutable recommendation contracts, complete-plan/policy validation,
and offline scenarios. Broker models and reconciliation are removed from active
code; the original implementation remains in Git history. SQLite persistence is in progress; FMP, AI and
Telegram integrations are still pending. Resume at the first unchecked step.

## Run the offline foundation

Install Python 3.12+ and uv, then run:

```sh
uv sync --locked
uv run python -m nomy_trader.scenarios
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

Pydantic validates immutable external contracts. pytest checks behavior, Ruff
formats/lints Python, mypy checks types, and Hatchling builds the package. Exact
versions are in uv.lock. Scenarios require no services or credentials. All
prices, risk budgets and thresholds in fixtures are explicitly hypothetical;
no production risk configuration is supplied. Scenario health checks validate
rejection behavior, not real quota persistence or Telegram recovery.

Read AGENTS.md, PLANS.md, then docs/PRODUCT_SPEC.md, TRADING_POLICY.md,
ARCHITECTURE.md, DATA_MODEL.md, EVALUATION.md and ROADMAP.md. Numeric policy TBDs
remain unresolved. Original IBKR automation specifications are preserved under
[historical design](docs/archive/ibkr-design/README.md) for possible future work.

SQLAlchemy Core supplies transactional SQLite access; Alembic supplies versioned
schema upgrades. These dependencies implement the approved persistence milestone.
