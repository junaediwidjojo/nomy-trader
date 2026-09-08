# nomy-trader — Milestone 1 ExecPlan

Status: superseded by [MVP scope revision](001-mvp-scope-revision.md).
The prior implementation was approved and partially started, then paused on
2026-09-08 at the user’s scope change. This document is historical, not the
active implementation checklist.

## Goal and outcome

Create the first reviewable MVP increment: an installable Python package named
`nomy-trader` (import `nomy_trader`) that validates domain contracts and runs
deterministic synthetic scenarios offline. This milestone is a foundation,
not an operational trading system. Implement only Roadmap Milestone 1.

## Scope and non-goals

Include typed Event, Evidence, Decision, TradePlan, ThesisVersion, Order, Fill,
and reconciliation contracts; validation helpers; synthetic examples; tests;
and documented verification commands.

Exclude provider calls, model execution, broker execution, scheduling, database
persistence, historical scanning, backtesting, position sizing, and a UI.
SQLAlchemy, SQLite migrations, and Alembic belong to Milestone 6. No live mode.

## Existing specifications

The repository currently contains documentation only and has no Git metadata.
Read AGENTS.md, PLANS.md, docs/PRODUCT_SPEC.md, docs/TRADING_POLICY.md,
docs/ARCHITECTURE.md, docs/DATA_MODEL.md, docs/EVALUATION.md, docs/ROADMAP.md,
docs/BROKER_DUE_DILIGENCE.md, and docs/decisions/001 through 004 before execution.
HANDOFF_PROMPT.md explicitly scopes the first increment to this milestone.

## Specification review and proposed design

- Use Python 3.12+, uv, a src-layout package, and Pydantic for contracts.
  Use pytest for behavior, Ruff for formatting/linting, and mypy for typing.
  Document dependency purposes and lock resolved versions. Defer dependencies
  with no use in this milestone.
- Use immutable models, reject unknown fields, validate finite Decimal values
  for prices/quantities, and reject naive datetimes. Normalize aware timestamps
  to UTC. Reject malformed model output rather than silently correcting it.
- Require explicit identifiers and version metadata. Evidence retains content
  or a licensed reference, source, publication/retrieval times, and a content
  hash. Revision history creates new objects. Storage-level append-only
  enforcement remains a Milestone 6 responsibility.
- Validate decision evidence references in an aggregate context, including
  event ownership and availability by decision time. Publication time alone
  cannot establish historical availability: retrieval and snapshot/version
  metadata must also precede the simulated decision. Late revisions fail.
- Model all documented decision actions, including RAISE_STOP from the product
  specification. A decision recommendation is never an authorization or fill.
- A complete TradePlan requires explicit entry ceiling, bear/base/bull values,
  fair-value and target ranges, hard stop, expected and maximum duration,
  partial-exit policy, thesis, assumptions, observable invalidations, evidence,
  confidence, uncertainty, and strategy/model/prompt version information.
  Validate positive ordered ranges, stop below entry, and expected duration
  no longer than maximum duration. Synthetic values are examples, never defaults.
- Keep filled price/quantity in execution facts linked to plans; an unfilled
  plan must not fabricate them. Risk budget is explicit input from deterministic
  policy, not an LLM-calculated position size. Full risk logic is deferred.
- Define documented order and plan states without implementing the persistent
  lifecycle engine. UNKNOWN is a recovery condition requiring reconciliation,
  never proof of rejection and never permission to resubmit.
- Define pure reconciliation checks on synthetic snapshots: each nonzero broker
  position maps to exactly one active plan, quantities agree, and unknown
  submissions or failed session/data/protection checks block new orders.
  An active plan without a position requires reconciliation of order history;
  do not automatically close it. No protective-order repair is executed here.
- For synthetic execution facts, repeat identical execution IDs or
  acknowledgements without duplicating fills; conflicting facts with the same
  identity fail validation. This does not claim broker submission idempotency.

Alternative considered: implement the full ten-milestone system immediately.
Rejected because the roadmap requires separate reviewable milestones and
unresolved research policy cannot safely become executable defaults.

## Data model and API changes

Create `src/nomy_trader/domain/` for models, enums, and pure aggregate validation.
Create `src/nomy_trader/scenarios.py` with a deterministic scenario runner,
invoked through `uv run python -m nomy_trader.scenarios`. Its report identifies
each case and expected validation or reconciliation result. Add `tests/`.
Update DATA_MODEL.md to distinguish contract validation from later persistent
state transitions and align decision actions with PRODUCT_SPEC.md.

## Safety and failure behavior

There is no callable broker or network execution path. Execution mode accepts
paper only. Retrieved content is inert evidence data. Unsupported actions,
missing exits, future evidence, inconsistent references, invalid numeric values,
and ambiguous execution facts fail explicitly. Model availability cannot
override deterministic safety checks. A validated plan alone cannot authorize
an order. Exchange-session calculations are deferred rather than approximated
with hand-coded market hours.

## Ordered implementation steps

1. After approval, record approval and inspect Python/uv availability.
2. Add packaging, dependency lock, ignore rules, and verification configuration.
3. Implement contracts and pure cross-record validators.
4. Add synthetic fixtures and scenario runner with stable output.
5. Add success/failure tests, including duplicate execution evidence handling.
6. Update README, data-model documentation, dependency rationale, and this plan.
7. Run all verification commands and record exact outcomes and limitations.

## Acceptance criteria and validation

Run `uv sync --locked`, `uv run ruff format --check .`, `uv run ruff check .`,
`uv run mypy src`, `uv run pytest`, and the scenario runner. Dependency setup may
need network access; scenario execution and tests must require no external
services, credentials, or accounts.

Tests must cover valid and incomplete trade plans; invalid ranges/durations;
NaN/infinity; naive timestamps; unknown fields and unsupported AI actions;
missing, mismatched, late, and revised evidence; immutable thesis revisions;
paper-only mode; duplicate/conflicting fills and acknowledgements; orphan and
multiply mapped broker positions; quantity mismatch; unknown submission;
and stale-data/session/protection failures. Cover the eleven synthetic scenario
categories in EVALUATION.md, using fixed facts rather than pretending to infer
event causes. Model-outage scenarios verify that safety checks are independent
of model availability, not that a real exit can be executed.

Completion requires all commands passing, deterministic scenario results, and
an accurate distinction between validated contracts and deferred operational
guarantees. Do not claim strategy returns or real broker behavior are tested.

## Rollback and recovery

This increment creates no remote state or database. Remove the newly added
package/configuration/tests to revert implementation; retain original specs.
Do not overwrite unrelated user files. Git is not initialized; do not assume
checkout/reset is available. If setup or validation fails, record the failure
and leave the milestone incomplete until resolved.

## Decisions and unresolved TBDs

Approval requested: this Milestone 1 scope and proposed contract semantics.
Project name `nomy-trader` is already user-approved.

Preserve all trading-policy TBDs: minimum price, market capitalization, dollar
volume, maximum spread; return window; absolute and standardized decline;
relative volume; margin of safety; partial-exit rules; risk per trade; position
weight; concurrent positions; sector concentration; daily/weekly loss gates;
and aggregate open risk. They require later hypotheses, experiments, and
approval. Freshness limits, confidence meaning, duration/session conventions,
valuation methodology, and reconciliation recovery authority also need explicit
operational definitions in later milestones. Contract examples do not settle
these policies. Broker eligibility and historical evidence licensing remain
outside this increment.

## Progress and deviations

- Read the specification bundle and identified the absence of an ExecPlan.
- Updated the README project name to `nomy-trader`.
- Prepared this plan; no implementation code or tests have been added.
- No deviations from the roadmap.

Historical progress correction: partial package, contracts, validation, scenarios
and tests now exist. Verification was not finalized. See the revised plan’s
resume inventory; do not execute this superseded plan.
