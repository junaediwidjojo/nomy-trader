# nomy-trader

Educational, AI-assisted buy-side recommendations: FMP candidate discovery,
deterministic eligibility and advisory sizing, complete trade plans logged to
SQLite, and Telegram notifications. The user executes independently elsewhere.
No broker integration, position tracking, reconciliation or automated exits.
Stop and target fields are advisory; profitability is not assumed.

## Current status

The revised [ExecPlan](docs/plans/001-mvp-scope-revision.md) is awaiting approval.
Partial offline domain code from the preceding scope exists but has not been
accepted or fully verified. Implementation is paused; do not treat it as a
working recommendation pipeline. Resume from the ExecPlan checklist after approval.

Read AGENTS.md, PLANS.md, then docs/PRODUCT_SPEC.md, TRADING_POLICY.md,
ARCHITECTURE.md, DATA_MODEL.md, EVALUATION.md and ROADMAP.md. Numeric policy TBDs
remain unresolved. Original IBKR automation specifications are preserved under
[historical design](docs/archive/ibkr-design/README.md) for possible future work.
