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
code; the original implementation remains in Git history. SQLite journal/outbox/quota
persistence and FMP loser discovery are implemented; AI and Telegram integrations
are still pending. The verified FMP free account can list 50 losers but returned
HTTP 402 when rechecking a live loser quote, so it cannot yet produce a reliable
dynamic-candidate recheck. Resume at S12 only after resolving that provider gate.

## Run the offline foundation

## Massive registration for the approved recheck provider

1. Register at https://massive.com/dashboard/signup.
2. Select Stocks Basic ($0/month), for personal use. This provides end-of-day
   data at five API calls per minute; no paid subscription is needed for this test.
3. Find your API key in the Massive dashboard.
4. Add `MASSIVE_API_KEY=your_key_here` to the existing local `.env`, keeping
   `FMP_API_KEY` as well. Never paste either key into chat or commit it.
5. Resume S12a in the ExecPlan to verify actual candidate coverage before use.

Massive integration is approved but not implemented yet. Its free bars do not
provide real-time bid/ask quotes. Official setup:
https://massive.com/docs/rest/quickstart

## Offline verification

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
schema upgrades. `httpx` provides the bounded FMP HTTP client and
`python-dotenv` loads the ignored local `.env`; neither logs or persists the API
key. These dependencies implement the approved persistence and FMP milestones.

## Resume checkpoint

S01–S08 are complete. S09 needs an FMP key provisioned locally as `FMP_API_KEY`
before account entitlement can be verified. Do not put keys in chat or Git.
The MVP is not yet operational: no FMP/model/Telegram adapters, delivery worker
or scheduler exist. Advisory sizing is validated from supplied inputs; final
quantity selection remains S19. Remaining policy decisions are in the ExecPlan.

Verification on Python 3.14.6: locked sync, format, lint, mypy, 75 tests and
12 offline scenarios pass. Other supported Python versions remain untested.
