# nomy-trader — FMP and Telegram recommendation MVP ExecPlan

Status: implementation approved by user on 2026-09-08. Recommendation-domain
foundation in progress. Unspecified policy values remain unset. This supersedes 001-domain-contracts.md for active
work. The ten numbered sections below follow PLANS.md.

## 1. Goal and user-visible outcome

Discover abnormal stock declines using FMP, investigate evidence, calculate a
complete buy-side TradePlan and suggested size deterministically, save the full
recommendation in SQLite, and notify the user through Telegram. The system ends
at notification. The user independently chooses whether, where, at what price,
and at what size to buy in an unrelated app. Delivery is not execution.

## 2. Scope and explicit non-goals

Include FMP free-tier discovery, deterministic eligibility, bounded AI analysis,
deterministic valuation and advisory sizing, complete plans, an immutable SQLite
recommendation journal, outbound Telegram delivery, quota-aware scheduling, CLI
status/export, and informal manual benchmarking.

Drop from this MVP: all broker connectivity, broker position tracking,
reconciliation, orders, fills, automated sells/exits and portfolio monitoring.
Stop/target/duration/invalidation fields remain instructions in the proposed
plan; no code monitors or executes them. Defer Telegram confirm/reject interaction
as a fast-follow. Defer formal AI-versus-baseline backtesting, real automation,
and IBKR integration to separately approved future plans. No live-trading mode,
UI dashboard, embeddings, or automated fill ingestion.

## 3. Relevant existing modules and specifications

Read AGENTS.md, PLANS.md and the current PRODUCT_SPEC, TRADING_POLICY,
ARCHITECTURE, DATA_MODEL, ROADMAP and EVALUATION documents. ADR 005 records the
scope change; docs/archive/ibkr-design preserves the original six specifications.
ADRs 002/004 and BROKER_DUE_DILIGENCE are historical future-direction material.

Resume inventory: the previous approved scope already produced pyproject.toml,
uv.lock, .gitignore, src/nomy_trader/domain/{models,validation}.py,
src/nomy_trader/scenarios.py and tests/test_domain.py. They contain offline broker
contracts/checks which are NOT the revised MVP design. No provider implementation
exists. Python 3.14.6 and a local .venv were used. uv was installed at
/private/tmp/nomy-tooling/bin/uv; this temporary path may disappear. Dependency
cache was /private/tmp/nomy-uv-cache. Initial mypy passed, but formatting/lint and
test verification was not finalized before the scope changed. Do not infer
completion or reuse broker requirements from those files. The directory has no
Git repository; there are no commits to resume from yet.

## 4. Proposed design and alternatives considered

Flow: exchange-session scheduler -> FMP losers/screener -> independently
recomputed eligibility using FMP quote/volume/history -> time-bounded evidence
-> typed AI classification -> deterministic valuation and advisory risk/sizing
-> validate complete plan -> commit recommendation and notification intent in
one SQLite transaction -> Telegram outbound worker -> delivery status journal.

Use Python 3.12+, uv, Pydantic, SQLite, SQLAlchemy and Alembic in one modular
process. Keep market data, evidence, AI and notification providers behind
interfaces. Use httpx for HTTP; introduce scheduling/calendar dependencies only
with documented purpose. Retain OpenAI for analysis. News/disclosure providers
and their coverage are an approval gate, not assumed part of FMP free access.

FMP is the requested Option A for market-wide candidate discovery. Prefer one
losers/screener request over per-symbol polling; paginate only if documented and
budgeted. Prefer entitled batch quote calls; otherwise cap candidate enrichment
within the daily budget. Never equate a movers list with complete universe
coverage or trust its ranking as proof of eligibility. Missing spread, halt,
volume, volatility or other required fields blocks eligibility until the data
or an explicitly approved policy change exists.

Provider feasibility checked against official public documentation on 2026-09-08:
[FMP pricing](https://site.financialmodelingprep.com/developer/docs/pricing)
lists Basic at 250 calls/day and describes end-of-day data;
[losers API](https://site.financialmodelingprep.com/developer/docs/stable/biggest-losers)
documents the intended discovery capability. Account-specific entitlement,
symbol coverage, batch access, freshness, quota reset semantics, bandwidth and
permitted private Telegram display remain unverified. Do not silently purchase
a plan, switch provider or pretend delayed quotes are live if validation fails.

Persist a quota ledger; reserve a call before making it and conservatively count
failed/ambiguous requests. All FMP consumers share this ledger, including retries,
evidence and optional benchmarking calls. Gate each scan by remaining budget:
scans * discovery calls + bounded enrichment + evidence + retries <= approved
usable daily budget. Schedule frequency, enrichment cap, reserve, cache age and
reset boundary remain decisions below. Restart must not reset usage. No bursts
to catch up missed scans. Exhaustion pauses work until the verified reset.

Sizing is advisory arithmetic using explicitly configured capital/risk inputs,
entry ceiling and stop. Never infer actual cash, positions, fills, realized loss
or exposure from prior recommendations. The model cannot size the trade. The
choice of manual portfolio inputs versus explicitly unavailable portfolio gates
needs approval before any recommendations ship. No missing input becomes zero
exposure. Stops are proposed prices, not guaranteed or installed protection.

Telegram includes plan ID/time, symbol, suggested entry ceiling, deterministic
suggested shares or dollar value, sizing basis, stop, targets, thesis summary,
confidence/uncertainty, and a statement that execution is manual. The full plan
is always in SQLite. Plain text avoids untrusted markup. Bound summary size;
never truncate required fields. No buttons, reply polling or webhooks.

Use a transactional outbox: PENDING -> SENDING -> SENT, FAILED, or UNKNOWN.
Record attempt times and Telegram message ID on confirmed success. A timeout or
crash after dispatch becomes UNKNOWN; do not automatically resend ambiguous
messages. Delivery cannot be exactly-once across SQLite and Telegram. A known
429 can be retried after provider retry-after subject to expiry and bounded
retry policy. Unknown outcomes are visible in CLI status, not treated as sent.
No delivered/read guarantee and no order state is implied.

Alternatives: original broker automation is deferred; per-symbol market polling
is rejected for quota efficiency; sending before committing is rejected because
it permits unlogged recommendations. Formal backtesting is deferred in favor of
an exportable forward recommendation log. No portfolio enforcement is claimed.

## 5. Data-model or API changes

Retain Event, immutable Evidence/version provenance, Decision, valuation and
complete TradePlan contracts. MVP analyst actions are REJECT, WAIT, PROPOSE_BUY;
sell actions and broker entities leave the active recommendation flow.

Add versioned policy/sizing inputs with source/as-of time, proposed quantity or
notional and formula results. TradePlan retains all advisory exit fields and
strategy/model/prompt versions; filled price and quantity are inapplicable.
Add Recommendation (immutable full serialized plan, schema version, event ID,
created_at, quote_as_of, policy version, idempotency key) and NotificationAttempt
(outbox identity, status, attempted_at, sent_at, provider message ID, sanitized
error). Unique notification intent prevents duplicate local queue entries.
Preserve all attempts; never overwrite evidence or a sent plan with a revision.

Add scan runs, cached responses/provenance, persistent FMP quota reservations and
system health for data, providers and delivery. No cash/position/fill authority.
Interfaces: discover candidates; fetch quotes/history; retrieve evidence;
analyze; calculate valuation/size; store recommendation and outbox; send text;
export sent/failed/unknown recommendations. Suggested size is separate from any
optional future user-entered actual trade. Manual comparison is export-only in
MVP; no actual-trade capture UI or automated outcome/P&L engine.

## 6. Safety invariants and failure behavior

No broker code path, broker credentials, order submission or execution mode.
Recommendations require complete evidence-backed plans and approved deterministic
policy. Reject malformed/unsupported AI outputs; never repair them silently.
Treat source text and tool responses as untrusted data. UTC timestamps and
exchange calendars govern sessions; preserve point-in-time source versions.

Missing policy inputs, stale/unavailable required data, exhausted quota, invalid
valuation or unavailable evidence prevents a buy notification and records a
reason. Model failure never creates a fabricated plan. Database failure prevents
sending; Telegram failure retains the durable recommendation. Revalidate plan
age before delayed delivery; expired plans are not sent. Redact tokens, query
API keys, chat IDs and sensitive capital settings from logs and commits.
No suggestion can enforce how the user buys or guarantee a stop will execute.

## 7. Ordered implementation steps

Resume protocol: read this file first; start at the first unchecked approved
step. Complete one small step and its targeted verification, then update its
checkbox and commit code plus this file together. Each completion note records
commands/results and relevant limitations. If interrupted, leave an indented
`Resume:` note with files changed, what works, the exact next action and failing
checks. Do not check off partial work. Run the full suite at milestone boundaries.
Until Git exists, do not claim a commit; setup is the first approved work step.

- [x] P00: Draft the revised ExecPlan and update affected specs; preserve the
  original design under docs/archive/ibkr-design. Documentation-only revision.
- [x] P01: Plan implementation approved on 2026-09-08, including local Git
  initialization and step commits (D09), and conservative UNKNOWN handling
  (D08). D01–D07 and remaining D08 configuration are still unresolved; approval
  supplies no numeric values. Independent foundation work proceeds with required
  inputs and synthetic fixtures only; dependent production behavior stays blocked.
- [x] S01: Initialize local Git, audit ignore rules for secrets/caches, and commit
  the current baseline plus plan without remote publication. Verify git status.
  Completed: ignored caches, environment files, local databases/logs/exports;
  staged only specifications, packaging, source and synthetic tests. Baseline
  commit retains old broker code for history; active removal is S03.
- [x] S02: Inspect prior partial implementation; run existing checks and record
  results. Classify reusable recommendation contracts and deferred broker code.
  Completed: baseline 309c5f0; 46 tests pass, mypy passes, format passes; Ruff
  reports UP047 in validation and E501 in scenarios. Reuse Event/Evidence,
  Decision, valuation, TradePlan and immutable revisions. Remove broker state,
  order/fill/position models, reconciliation and their scenarios in S03.
  Existing tests pass old requirements only, not the revised MVP.
- [x] S03: Refactor active domain contracts for recommendations/advisory sizing;
  remove broker coupling from MVP APIs and scenarios. Verify contract tests.
  Completed: removed order/fill/position/reconciliation and sell-action contracts;
  added explicit SizingInputs, SuggestedSize, Recommendation and immutable
  NotificationAttempt contracts. Retained advisory exit content. 38 tests pass,
  mypy and targeted Ruff pass. Remaining scenario replacements are S05.
- [x] S04: Add complete-plan/policy-context validators and invalid-output tests.
  Completed: explicit policy/clock/health context, evidence retrieval timing,
  buy-decision links, size arithmetic/budgets, quote age and expiry validators.
  59 tests and mypy pass; Ruff/format pass. No runtime policy defaults introduced.
- [ ] S05: Replace broker scenarios with notification/freshness/quota scenarios;
  run offline scenario command and full domain verification.
- [ ] S06: Add SQLAlchemy models and first Alembic migration for immutable plans,
  evidence, recommendations and outbox. Test upgrade and foreign keys.
- [ ] S07: Implement atomic recommendation/outbox writes and unique local intent;
  test rollback and repeated writes without duplicate recommendations.
- [ ] S08: Add quota/cache/scan-run migration and persistent reservation API;
  test restart accounting and configured reset boundary.
- [ ] S09: Verify FMP account endpoint/field entitlements with minimal sanitized
  requests; record actual quota cost and freshness. Stop if D01 is unsatisfied.
- [ ] S10: Implement FMP HTTP wrapper with typed response models and redaction;
  test malformed payload, authentication, timeout and server failures offline.
- [ ] S11: Implement losers/screener discovery and rate-limit handling through
  the quota API; test pagination caps, 429 and budget exhaustion.
- [ ] S12: Implement entitled quote/history enrichment and cache freshness;
  test missing fields, stale timestamps and batch/per-symbol budget bounds.
- [ ] S13: Implement deterministic candidate filters from approved parameters;
  verify boundary cases and no silent fallback for absent required fields.
- [ ] S14: Implement event deduplication across scans and restarts; test repeats
  and materially new events under approved deduplication rules.
- [ ] S15: Implement approved evidence-provider wrapper and immutable provenance;
  test availability/version timestamps and unavailable primary evidence.
- [ ] S16: Add bounded evidence context construction; test conflicting sources,
  future/revised evidence and instruction-like retrieved text.
- [ ] S17: Implement OpenAI adapter and strict structured analyst outputs;
  test malformed output, unsupported citations/actions, timeout and refusal.
- [ ] S18: Implement approved deterministic valuation formulas with explicit
  assumptions; verify arithmetic and invalid valuation rejection.
- [ ] S19: Implement approved advisory sizing and risk applicability policy;
  test absent/stale capital inputs, rounding and all approved limit boundaries.
- [ ] S20: Assemble and persist complete recommendations; test every missing
  required field and ensure rejected cases never queue a notification.
- [ ] S21: Implement Telegram plain-text renderer; test all mandatory fields,
  uncertainty, manual-execution wording and message-length constraints.
- [ ] S22: Implement outbound Telegram adapter using a fake transport first;
  test success, 429, definite failure, timeout and secret redaction.
- [ ] S23: Implement outbox dispatch/recovery and expiry checks; test crash
  windows, UNKNOWN handling and no automatic ambiguous resend.
- [ ] S24: Implement CLI status and recommendation JSON/CSV export; verify full
  TradePlan/timestamps and sent versus failed versus unknown classifications.
- [ ] S25: Add quota-aware exchange-session scheduling with approved cadence;
  test holidays, restarts, exhausted budget and no catch-up request burst.
- [ ] S26: Add local daily operational report and manual benchmarking guide;
  verify no assumed fills, fabricated returns or portfolio claims.
- [ ] S27: Run end-to-end fixture pipeline through SQLite and fake Telegram;
  verify durable log before delivery and every rejection/failure boundary.
- [ ] S28: Run full formatting/lint/type/tests/scenarios; record exact results
  and current limitations. Document Mac setup and Linux supervision/recovery.
- [ ] S29: With configured credentials and explicit approval to send a test
  message, perform one controlled FMP-to-Telegram smoke test; record sanitized
  evidence. No broker or order checks. Mark MVP complete only after gates pass.

## 8. Test and validation plan

Use uv sync --locked, uv run ruff format --check ., uv run ruff check .,
uv run mypy src, uv run pytest and uv run python -m nomy_trader.scenarios.
Tests use fixture transports and no credentials. Validate schema completeness,
Decimal arithmetic, UTC handling, evidence time/version references, deterministic
sizing and policy gaps. Cover quotas at reset/restart boundaries, all HTTP failure
classes, database rollback, duplicate events, outbox crash windows, unknown
Telegram outcomes and expiry. Test migrations in disposable SQLite databases.
Full integration must prove each sent recommendation was saved with all plan
fields beforehand; delivery status must never masquerade as execution.

Informal evaluation exports every sent recommendation with plan and send times;
unknown/failed attempts remain separately visible. User compares stock movement
and independently recorded actions manually. No inferred fill, realized P&L,
AI superiority or historical strategy claim. Domain scenarios retain temporary,
structural/governance, sector, no-news, conflicting and revised evidence cases;
broker scenarios are replaced by quota, delivery and persistence failures.
Documentation revision verification checks links, required ten headings,
checkbox syntax and active-versus-historical scope consistency; no code tests
are required to approve this documentation-only change.

## 9. Rollback or recovery approach

Original six specifications are preserved verbatim in docs/archive/ibkr-design;
ADRs remain historical. Prior partial code is left untouched during this planning
revision. No database, provider request with credentials or Telegram send is
created by this revision. Approval does not erase original design history.

During implementation, commit small steps; roll back code without deleting
recommendation history. Back up SQLite before migrations, test restoration, and
retain unresolved outbox attempts on restart. Never resend UNKNOWN messages
blindly. If quota/entitlements are incompatible, stop affected steps and record
proof plus requested decision under the checklist, without adopting paid access.

## 10. Open decisions requiring user approval

D01 — FMP feasibility: confirm losers/screener, quote/volume/history and required
filter field access on the actual free account. If only delayed/EOD data or
insufficient fields are available, approve an EOD policy change, narrower scope,
or another explicit revision; do not silently bypass filters or upgrade.

D02 — Discovery policy: all existing minimum price, market cap, dollar volume,
maximum spread, return window, absolute/standardized decline and relative volume
TBDs remain. Approve universe/candidate caps, event deduplication definition and
freshness/notification expiry. A screener changes discovery, not eligibility.

D03 — Budget: approve scan frequency/session window, candidate enrichment cap,
retry/reserve allocation, cache TTL and account reset semantics after D01.
The published 250/day ceiling is not 250 scans/day or an assumed batch entitlement.

D04 — Advisory sizing: specify reference capital or per-recommendation budget,
risk per trade, maximum suggested position weight/notional, quantity versus USD
presentation, rounding/fractional-share convention and input validity period.
No default capital or risk percentage. Missing required inputs blocks release.

D05 — Portfolio limits: explicitly decide whether maximum concurrent positions,
sector concentration, daily/weekly loss gates and aggregate open risk are deferred
as unverifiable, or evaluated against user-supplied dated snapshots. No broker
means they cannot be enforced against actual holdings. No averaging down can be
a stated manual constraint, but cannot be verified without holdings. Recommend
retaining strict per-recommendation checks; user must approve portfolio policy.

D06 — Plan policy: margin of safety, deterministic valuation methodology, stop
and target construction, expected/maximum duration conventions and partial-exit
TBDs still need approval because the recommendation contains those fields, even
though automated exit logic is dropped. Define confidence semantics and required
uncertainty disclosures; never label confidence a calibrated success probability.

D07 — Evidence and AI: choose entitled news/primary/financial-context sources,
minimum evidence sufficiency, model and cost cap. FMP free market data does not
establish news/fundamental coverage or permission to redistribute source text.

D08 — Telegram operations: private destination, credential provisioning,
notification volume cap/cooldown, expiry, retry limits and UNKNOWN outcome policy.
Proposed conservative default is no automatic ambiguous resend; approval needed.
No confirm/reject interaction. Confirm permitted private data display under FMP
terms before real sending; no message is sent during planning.

D09 — Approve local Git initialization/step commits, release checklist and the
recommendation-only safety agreement changes. Current worktree has no Git; future
resume notes must include commit IDs once available. Original paper-only rule
constrains any future system execution; the MVP does not control the user's
external app or authorize a live broker integration.

Decision update 2026-09-08: user selected D05 portfolio limits unavailable,
with per-recommendation checks only, and delegated D04 sizing recommendations
to the assistant. No actual capital amount was provided; any chosen reference
capital must be labeled hypothetical, never presented as actual holdings.

D04 recommendation delegated by user: hypothetical USD 10,000 reference,
USD 25 planned loss-at-stop budget (0.25%), USD 500 notional cap (5%), whole
shares rounded down, explicit dated inputs. This is an educational example,
not actual capital or a recommendation to invest that amount. S19 will implement
quantity selection; fixtures currently supply arithmetic for validation only.
Stop-based loss is not a maximum loss guarantee (gaps/slippage/fees apply).
D05 approved: portfolio limits unavailable; no portfolio enforcement claims.
