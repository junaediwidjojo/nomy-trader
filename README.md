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

Twelve Data Basic is now the approved price/volume recheck provider. Its free
plan supplies eight API credits per minute and a daily allocation, with a
limited-venue U.S. real-time reference feed. This is useful for confirming a
shortlist, but is never an executable/consolidated quote or proof of eligibility.
The current Massive end-of-day adapter remains deferred: its first real response
was stale, with bars through 2026-09-04 while the required completed XNYS session
was 2026-09-08. No plan or recommendation was created.

The approved large-cap discovery policy requires price at least $10 and market
capitalization at least $2 billion. FMP's screener endpoint returned HTTP 402 for
this account, so this filter is currently a provider gate; the system must not
mislabel price-only candidates as large-cap stocks.

The active replacement is a transparent, manually maintained seed list at
[`config/large_cap_universe.json`](config/large_cap_universe.json). FMP loser
results are narrowed to this list and the $10 price floor, while retaining raw
source candidates in SQLite. Review the list before each policy release; it does
not automatically prove current market cap, liquidity, or eligibility.

## Run the offline foundation

## Twelve Data registration for the approved recheck provider

1. Register at https://twelvedata.com/.
2. Select Basic ($0/month), for personal/internal non-display use.
3. Find your API key in the Twelve Data dashboard.
4. Add `TWELVE_DATA_API_KEY=your_key_here` to the existing local `.env`, keeping
   `FMP_API_KEY` as well. Never paste either key into chat or commit it.
5. Resume S12t-b in the ExecPlan to verify actual candidate coverage before use.

The typed Twelve Data quote adapter and persistent 8-credit-per-minute,
800-credit-per-day local reservation guard are implemented and covered by
offline fixture tests. It has not yet made a live request. The free feed does
not establish a consolidated bid/ask or executable price. Official pricing:
https://twelvedata.com/pricing

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
