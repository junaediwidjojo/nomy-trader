# nomy-trader — FMP and Telegram recommendation MVP ExecPlan

Latest approved direction: user approved Twelve Data Basic as the recheck
provider, retaining FMP biggest-losers discovery. This supersedes the attempted
Massive Stocks Basic end-of-day recheck because Massive had not published the
latest completed XNYS session. Use local TWELVE_DATA_API_KEY alongside
FMP_API_KEY. No paid subscription is authorized. Twelve Data's free U.S. feed
is a limited-venue reference and must never be presented as an executable
consolidated quote; missing spread/halt/fundamental fields still cannot silently
pass eligibility. Massive code and the stale-data finding remain retained as a
deferred provider alternative, not an active dependency.

Status: implementation approved by user on 2026-09-08. Recommendation-domain
foundation and SQLite persistence milestones complete; S09 awaits FMP credentials. Unspecified policy values remain unset. This supersedes 001-domain-contracts.md for active
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

Twelve Data Basic is the approved replacement for price/volume rechecks. Its
published free quota is eight API credits per minute and 800 per day; each
endpoint and requested symbol has an explicit documented credit weight. Reserve
the conservative maximum required credits before dispatch, including failures;
never assume a batch endpoint costs one credit without a documented response or
account verification. Use its typed price/time-series response only to confirm
the observed market state of a bounded shortlist after FMP discovery. Record
provider/source timestamps, endpoint, requested symbols, quota reservation and
venue-coverage limitation. Reject stale, missing, mismatched or incomplete
data. No recommendation may claim a live, NBBO, consolidated-volume or
executable quote based on this feed.

Universe decision approved 2026-09-09: limit discovery to U.S.-listed common
stocks with price strictly greater than $5 and market capitalization strictly
greater than $100 million.
These remove the current microcap/penny-stock failure mode. Average daily dollar
volume, maximum spread, exact allowed exchanges and a reproducible common-stock
classification source remain unresolved; their absence blocks eligibility and
recommendations. First verify the FMP screener's account entitlement and fields
with one quota-reserved request. If it cannot provide this universe, preserve
the original losers list as discovery-only and request a provider/policy decision
rather than inferring market cap from price or manually cherry-picking symbols.

2026-09-09 revised decision: the user selected a manually maintained large-cap
seed universe after the FMP screener returned HTTP 402. This is an explicit,
versioned allow-list, not a live claim about index constituents or market cap.
Every member is manually reviewed as a U.S.-listed common stock at list revision
time; list provenance, reviewer, revision date and the >$5/>$100M policy are stored
with each scan. FMP losers are intersected with this list and then checked against
the >$5 discovery price floor. List maintenance/review cadence remains an open
release decision. Missing liquidity/spread requirements still prevent eligibility.

2026-09-09 execution-venue decision: the user trades manually through Ajaib,
whose U.S.-stock selection is a changing subset of listed U.S. securities.
Treat Ajaib catalogue membership as a mandatory, fail-closed discovery gate. Do
not add a broker connection or scrape/login to the user's account. Store the
user-supplied crawl as a versioned local reference catalogue and preserve its
source/retrieval time/revision with each scan. A ticker absent from or ambiguous
in that catalogue stops before evidence/analysis. The user refreshes the local
catalogue by supplying a newer crawl; staleness is reported, not automatically
treated as a network failure.

2026-09-09 policy revision: broaden the Ajaib-listed universe to price >$5 and
market cap >$100M. This is only a discovery screen. It does not establish a
valid business, so recommendation eligibility additionally requires dated
evidence rejecting bankruptcy, delisting/halt, going-concern and material
dilution concerns. Lookback periods and quantitative financial-health tests
remain open decisions; absent evidence fails closed.

2026-09-09 discovery revision: FMP is the daily decline source. Make one
quota-reserved FMP biggest-losers request, intersect it with the imported local
Ajaib catalogue and use FMP daily history to validate the resulting shortlist.
Do not require a new Ajaib crawl each day. This is deliberately incomplete
coverage: the FMP-ranked feed can omit an Ajaib-listed stock with a smaller
decline, and no code may claim full-universe scanning on the free plan.

2026-09-09 proposed Ajaib discovery revision: use the public Ajaib US-stock
ranking endpoint as a candidate hint only if Ajaib supplies an authorized,
documented access method. The proposed request ranks by one-day percentage
change and should then apply the local availability/business screen plus a
short-term reversal hint: seven-day percentage change below an approved negative
threshold and one-month percentage change above zero. This is not an
eligibility rule, panic classification, buy signal, or substitute for FMP/Twelve
Data freshness and evidence. A direct Python request with a normal browser user
agent received HTTP 403 on 2026-09-09. Do not circumvent Cloudflare, use an
authenticated account, replay browser cookies, or scrape around that control.
Keep the FMP path active until an official method is approved and verified.

Availability-source feasibility: Ajaib's public catalogue is visibly paginated
through 66 pages and exposes symbol, price, change and market-cap values in the
browser-rendered view. A normal unattended HTTP request was blocked by Ajaib's
Cloudflare protection on 2026-09-09. Do not bypass it, scrape around it, or log
into the user's account. The MVP therefore needs a user-supplied exported list,
explicit in-app confirmation, or a separately authorized official Ajaib API/feed
before it can build a fresh complete snapshot. Until then, the Ajaib gate blocks
all expanded-universe candidates.

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
- [x] S05: Replace broker scenarios with notification/freshness/quota scenarios;
  run offline scenario command and full domain verification.
  Completed: 12/12 offline scenarios; 64 pytest tests. uv sync --locked
  --offline, Ruff format/check and mypy all passed on Python 3.14.6. Commands
  used UV_CACHE_DIR=/private/tmp/nomy-uv-cache and temporary uv path.
  Tests exercise domain health/notification facts, not real adapters. Updated
  README and data model. No new dependencies or production thresholds.
- [x] S06: Add SQLAlchemy models and first Alembic migration for immutable plans,
  evidence, recommendations and outbox. Test upgrade and foreign keys.
  Completed: migration 001, WAL/foreign-key setup and immutable journal triggers.
  Two migration/immutability tests and mypy pass. SQLAlchemy Core tables are
  the model layer; Alembic owns creation. Destructive downgrade deliberately
  requires backup restore. Initial missing FK column types fixed and retested.
- [x] S07: Implement atomic recommendation/outbox writes and unique local intent;
  test rollback and repeated writes without duplicate recommendations.
  Completed: journal validates context then commits source/plan/recommendation
  and outbox in one transaction. Conflicting immutable identities fail. Five
  storage tests pass, including injected outbox failure rollback, repeated
  intent and reopen durability. Mypy and Ruff pass. No send adapter exists.
- [x] S08: Add quota/cache/scan-run migration and persistent reservation API;
  test restart accounting and configured reset boundary.
  Completed: migration 002 adds immutable quota/cache/scan records. QuotaWindow
  requires explicit provider reset boundaries/call limit. BEGIN IMMEDIATE
  serializes reservations; no refunds on failure. Tests prove restart usage,
  explicit reset, overlapping-window rejection and 8 callers sharing 2 calls.
  Full milestone verification: 75 tests, 12 scenarios, uv locked sync, Ruff
  format/check and mypy all pass on Python 3.14.6 (offline). Cache ingestion
  and scan recording are intentionally deferred to their adapter steps.
- [x] S09: Verify FMP account endpoint/field entitlements with minimal sanitized
  requests; record actual quota cost and freshness. Stop if D01 is unsatisfied.
  Completed: 2026-09-08, three authenticated read-only requests returned HTTP
  200: `stable/biggest-losers` returned 50 rows with symbol/price/change/
  percentage/exchange; `stable/quote?symbol=AAPL` returned price, market cap,
  volume and timestamp; `stable/historical-price-eod/light?symbol=AAPL` returned
  date/price/volume (1,253 rows; requested limit was not honored). FMP dashboard
  accounting is unavailable through the API, so the verified local cost is three
  request initiations, not a confirmed provider-billed count. At 2026-09-08
  09:47 UTC the quote/history latest time was Friday 2026-09-04 20:00 UTC / date
  2026-09-04: appropriate only for an end-of-day recheck before the next U.S.
  session, never a live-intraday claim. FMP key was sourced locally and never
  printed. D01 is satisfied for end-of-day discovery/recheck only; spread/halt
  access and intraday freshness remain unavailable and must block any policy
  requiring them. Correction after the first real discovery-to-recheck attempt:
  the first live loser returned HTTP 402 from `stable/quote`, although AAPL
  worked. Therefore D01 is **not** satisfied for actual dynamic candidates:
  this free account offers discovery but cannot reliably enrich the discovered
  symbols. No Telegram send occurred.
- [x] S10: Implement FMP HTTP wrapper with typed response models and redaction;
  test malformed payload, authentication, timeout and server failures offline.
  Completed: `providers.fmp` loads the local ignored `.env`, exposes typed
  biggest-losers/quote/EOD-history calls and keeps the key out of exceptions and
  representations. Ten fixture-transport tests cover payload validation,
  auth/429/server errors and timeouts. A 2026-09-08 live adapter smoke check
  returned 50 candidates using the local key; no symbol or secret was logged.
  `httpx` provides bounded HTTP transport; `python-dotenv` makes the documented
  local `.env` setup work. S11 must consume quota reservations before each call.
- [x] S11: Implement losers/screener discovery and rate-limit handling through
  the quota API; test pagination caps, 429 and budget exhaustion.
  Completed: one FMP biggest-losers response is reserved before dispatch and
  persisted as an immutable ScanRun marked “potential candidates only.” The
  endpoint provides a fixed 50-row response and no documented pagination was
  exercised, so no pagination loop exists. Tests cover durable candidate logs,
  429 reservation retention and exhausted budget preventing a second HTTP call.
  A live run wrote one ScanRun to ignored `var/nomy-trader.sqlite`.
- [ ] S12: Implement entitled quote/history enrichment and cache freshness;
  test missing fields, stale timestamps and batch/per-symbol budget bounds.
  Approved replacement checklist (complete and commit each substep):
  - [x] S12a: User registered Massive Stocks Basic ($0) and provisioned
    MASSIVE_API_KEY in the ignored local .env. Actual BANL daily-bar access
    returned HTTP 200 without exposing the key.
  - [x] S12b: Add typed Massive daily OHLCV adapter and sanitized HTTP failures;
    test unavailable symbols, missing/invalid fields and auth/429 failures.
    Completed: strict adjusted OHLCV schema, bounded one-year requests, header
    authentication and redacted HTTP/data failures have fixture coverage.
  - [x] S12c: Add separate persistent rate accounting allowing no more than five
    Massive requests in any rolling minute, including retries/pagination.
    Completed: persistent immutable reservations, restart/concurrency tests and
    no automatic retry behavior. The published free-plan ceiling is used here.
  - [x] S12d: Replace active recheck with Massive completed-session bars; preserve
    source dates, validate session freshness and cache immutable observations.
    Never turn end-of-day bars into a live quote or fill missing policy fields.
    Completed: XNYS calendar chooses the latest completed session, including
    weekend/pre-market boundaries. Successful data persists until the next close;
    stale data is logged and rejected. Cache round-trip and stale refusal tests
    pass. A full recheck still requires data through the selected session.
  - [ ] S12e: Test and run one bounded FMP discovery-to-Massive recheck cycle;
    log data/limitations and update the active specs and next resume point.
  Resume: code and fixture tests are complete: a recheck reserves quote/history
  calls, verifies symbols and writes immutable cache snapshots. The 2026-09-08
  live recheck consumed the quote reservation then received HTTP 402 for the
  first actual loser; no cache was written. It must remain unchecked until D01
  is resolved with a free-tier-supported dynamic-candidate endpoint, explicit
  paid plan approval, or a revised scope. Do not retry or bypass filters.

  2026-09-09 Massive checkpoint: S12a is complete (key present and actual BANL
  daily data returned); S12b–d are implemented and under verification, but do
  not mark them complete until the end-to-end freshness gate passes. The first
  FMP discovery returned 50 candidates. Massive returned 88 daily bars for its
  selected candidate, with latest session 2026-09-04 / close 9.01 rather than
  the expected completed XNYS session 2026-09-08. The recheck recorded a safe
  provider/data failure and produced no cache, eligibility result, plan or
  notification. This is a validated stale-data refusal, not a strategy result.
  Full verification after the Massive checkpoint: Ruff format/lint, mypy and
  111 pytest tests pass. Resume at S12e after Massive publishes a current
  completed-session bar; do not lower the freshness requirement.

  2026-09-09 provider revision: user approved Twelve Data Basic after adding
  `TWELVE_DATA_API_KEY` to ignored `.env`. Massive is deferred as a possible
  paid/delayed-data alternative; do not remove its code or silently query it.
  Continue at the first unchecked Twelve Data substep below. Do not mark S12
  complete until S12t-e succeeds with current, typed recheck data.
  - [x] S12t-a: Record the approved provider replacement, free-plan credit
    constraints and limited-venue data limitation in this ExecPlan and README.
    Completed: 2026-09-09 after user provisioned the ignored local key; no
    external request or source code change occurred in this documentation step.
  - [x] S12t-b: Implement a typed Twelve Data read-only client for the minimal
    price and daily-time-series endpoints, with sanitized failures and no key in
    URLs, logs or exceptions. Add fixture tests for malformed payloads,
    authentication, rate limits and timeout.
    Completed: `providers.twelve_data` uses header authentication and a typed
    one-credit `/quote` response. Six fixture tests cover malformed data,
    authentication/server failure, 429, timeout and key redaction; targeted
    Ruff and mypy pass. Persistent credit accounting and a real request remain
    S12t-c through S12t-e.
  - [x] S12t-c: Extend persistent quota accounting with explicit Twelve Data
    credits (eight per rolling minute and an account-verified daily ceiling).
    Test multi-credit reservation, restart persistence and no automatic retry.
    Completed: reservations record one immutable row per credit atomically, with
    eight rolling-minute and 800 rolling-day caps. Tests cover seven-plus-one
    credit use, rejection at nine credits, boundary reset and invalid quantities.
    The quote CLI now uses this ledger; provider response-header reconciliation
    remains S12t-e.
  - [ ] S12t-d: Implement a provider-neutral recheck based on typed Twelve Data
    observations. Cache immutable successful data only through its stated
    freshness boundary; reject source-time ambiguity, stale daily bars, symbol
    mismatch, missing volume and insufficient history. Preserve the feed's
    coverage limitation in the result.
  - [ ] S12t-e: Run one bounded FMP discovery-to-Twelve Data recheck using the
    local keys. Record only sanitized result metadata, actual request/credit
    accounting and limitations. It produces a data observation only, never an
    eligibility pass, plan or notification.
    Resume: on 2026-09-09, the first saved FMP discovery candidate was `FCUV`.
    One live, read-only Twelve Data `/quote` request succeeded after reserving
    one local credit: source timestamp `2026-09-08T13:30:00Z`, close `5.91000`,
    previous close `17`, volume `1,365,300`. This is a single limited-venue
    observation only. S12t-e stays unchecked because S12t-d has not yet made
    the observation immutable, applied source-freshness rules, or reconciled
    the returned credit headers. No eligibility result, plan, or notification
    was created.
- [ ] S13: Implement deterministic candidate filters from approved parameters;
  verify boundary cases and no silent fallback for absent required fields.
  - [ ] S13a: Make one quota-reserved, sanitized FMP screener entitlement check
    for U.S. common-stock, price-at-least-$10 and market-cap-at-least-$2B fields.
    Record response shape, filter semantics, call cost and coverage; do not
    replace discovery until verified.
    Resume: 2026-09-09 read-only check to `stable/company-screener` with the
    approved $2B/$10/ETF-exclusion parameters returned HTTP 402 and no usable
    response. FMP screener entitlement is unavailable; do not implement against
    an undocumented or unaffordable endpoint. A price-only FMP-loser filter does
    not establish market cap. Select and verify a separate market-cap source, or
    explicitly revise the policy, before S13b/S13c.
  - [ ] S13b: Add versioned universe-policy configuration for the approved >$5
    and $2B floors, with required-but-unset average-dollar-volume/spread inputs.
    Test that missing liquidity fields block eligibility.
  - [ ] S13c: Switch discovery to the verified screener or deterministically
    intersect candidates with it; test boundary inclusions/exclusions, common
    stock classification and no results. Preserve source provenance.
  - [x] S13m-a: Create a reviewed, versioned large-cap seed-universe file with
    symbol, issuer name, security type, review date and list revision metadata.
    Test malformed, duplicate and non-common-stock rows fail closed.
    Completed: `config/large_cap_universe.json` contains 47 transparent initial
    U.S.-listed common-stock symbols and list/policy/reviewer metadata. The
    strict loader rejects malformed, duplicate and non-common-stock entries.
    It is a manually maintained seed, not a current market-cap assertion.
  - [x] S13m-b: Intersect the quota-accounted FMP biggest-losers result with the
    seed universe and approved price floor. Persist both raw discovery and the
    resulting shortlist plus policy/list provenance; test no-match and boundary
    behavior. This is discovery narrowing only, not eligibility.
    Completed: `discover_biggest_losers(..., manual_universe=...)` preserves raw
    FMP candidates, logs the narrowed list and immutable list/policy provenance,
    and returns the shortlist. Fixture tests cover no-match, price-floor boundary
    and provenance. A live scan on 2026-09-09 returned zero seed-universe
    matches: FMP's 50 most extreme decliners were all outside the list. This
    proves that intersecting a top-50 movers feed cannot discover a large-cap
    decline reliably; it created no recommendation or notification.
    Policy revision: price is strictly greater than $5 as of 2026-09-09. The
    seed configuration and boundary test are revised in the accompanying commit.
  - [x] S13m-c: Verify FMP daily-history access for a bounded sample of seed
    symbols and document per-symbol cost, latest-session freshness and response
    size. If viable within the 250-call daily budget, calculate and persist raw
    one-session returns across the manual universe in small quota-reserved
    batches. Do not apply an abnormal-decline threshold until D02 is approved.
    Resume: implementation and offline fixtures are complete in
    `market.universe_scan`; each symbol reserves a quota call before FMP history
    retrieval, rejects stale/incomplete history, calculates only raw one-session
    return, and persists a scan record. Targeted Ruff, mypy and two fixture tests
    pass. 2026-09-09 live sample used three quota-reserved daily-history calls;
    all returned latest completed XNYS session 2026-09-08: AAPL -1.17% (close
    316.22, volume 35,028,027), MSFT -1.15% (493.95, 18,684,730), NVDA -2.01%
    (225.73, 118,984,635). FMP's history endpoint delivers substantially more
    than the two required rows, so each call is capped to one symbol and only
    the two latest dated entries are retained in the raw scan result. Provider
    dashboard billing remains unverified; local accounting records three calls.
  - [x] S13m-d: Run one 47-symbol, quota-reserved raw-return scan of the seed
    universe. Present the observed declines without a panic threshold, and log
    all rejected/stale symbols. Do not label any result eligible or send it.
    Completed: 2026-09-09 scan made 47 local quota reservations and produced 25
    fresh 2026-09-08 observations. Largest raw declines: ABBV -2.96%, JNJ
    -2.22%, NVDA -2.01%, NFLX -1.89%, V -1.71%, JPM -1.43%. It safely rejected
    AVGO, LLY, MA, ORCL, HD, PG, MRK, CRM, ACN, MCD, IBM, CAT, NOW, TMO, PM,
    QCOM, AMGN, TXN, SPGI, BKNG, ISRG and ADP after FMP returned unusable
    history. No threshold, eligibility, plan or notification was produced.
  - [x] S13m-e: Add typed, immutable Ajaib catalogue-snapshot contracts and a
    manually reviewable local source file. Require catalogue provenance,
    retrieval time and unambiguous U.S.-stock symbol match; test absent and
    duplicate matches reject discovery. No account access or broker API.
    Completed: user supplied a JSON catalogue response with `APPROVED/OK` and
    739 entries. `config/ajaib_catalog_snapshot.json` preserves the 137 symbols
    matching >$5 and $300M–$10B as a dated revision, without copying unrelated
    icon URLs or treating it as a security-type classification. Strict loading
    and tests reject malformed and duplicate snapshots; FCUV is absent. The
    catalogue is deliberately local and manually refreshed rather than requiring
    an automatic Ajaib fetch.
    Policy revision: regenerate the derived symbol subset using price >$5 and
    market cap >$100M before S13m-f. Preserve the original 739-entry response
    count and reject zero/missing market-cap records. Validation of the supplied
    source found 532 entries matching the new numerical screen. The committed
    137-symbol snapshot remains the prior $300M–$10B derivation and is inactive
    pending replacement by a reproducible import of the user-provided 739-entry
    JSON; do not use it for the new policy.
    Update: `import_user_catalog` now validates and persistently records the full
    user-supplied response plus its derived working-symbol revision in SQLite.
    Fixture tests cover approved status, declared-count integrity, >$5/>$100M
    boundaries and durable reload. Next action is the controlled local import of
    the supplied 739-entry attachment; do not use the legacy 137 file afterward.
    Completed import: 2026-09-09 local SQLite import accepted the supplied
    `APPROVED/OK` response, preserved all 739 source entries and derived 532
    >$5/>$100M catalogue members under revision `ajaib-20260909T074453Z`.
    It made no network request, common-stock classification, decline claim,
    recommendation or notification.
    Latest import: 2026-09-09 local SQLite import accepted the newer supplied
    `APPROVED/OK` response with 862 entries and derived 608 >$5/>$100M working
    symbols under revision `ajaib-20260909T083116Z`. Its one-day, one-week and
    one-month price fields are retained as source data but are not yet used by a
    discovery or reversal-hint rule.
  - [ ] S13m-f: Intersect raw manual-universe observations with a current Ajaib
    snapshot and persist match/snapshot revision. Test no-match and stale
    snapshot behavior; present availability separately from any investment claim.
    Revision: replace Ajaib one-day-change ranking with FMP biggest-losers
    discovery intersected against the imported local catalogue. Preserve the
    one-request FMP quota cost and clearly record that the ranked feed is not
    complete universe coverage.
    Resume: `discover_biggest_losers` now accepts an Ajaib catalogue revision,
    intersects FMP candidates after reservation and records the revision with the
    raw/filtered scan. Five fixture tests, Ruff and mypy pass. Live check on
    2026-09-09 used the imported 532-symbol SQLite catalogue and one FMP
    biggest-losers request: 0 of the ranked 50 candidates matched. No candidate
    or recommendation was produced. This does not show that none of the 532
    stocks declined; it demonstrates the documented incomplete coverage of the
    ranked global feed. Next action: obtain approval for a complete daily
    universe source, or explicitly accept FMP as an extreme-move-only alert;
    do not use the legacy 137-symbol JSON file.
  - [ ] S13m-g: Verify an official, authorized Ajaib public-feed access method
    for the one-day-change-ranked US-stock endpoint. Record endpoint terms,
    authentication requirement, rate limits, response schema, source timestamp
    and the exact status of a single harmless request. Stop on 401/403, terms
    ambiguity, missing fields or inadequate freshness; never bypass access
    controls or use account cookies.
    Resume: a direct unauthenticated Python request with a standard browser
    user agent returned HTTP 403 on 2026-09-09. No data was retained and no
    retry/circumvention occurred. The next action is user-provided official API
    documentation or permission from Ajaib, not implementation.
  - [ ] S13m-h: If S13m-g verifies permitted access, add a typed, quota/rate
    limited Ajaib ranking adapter that stores an immutable raw response and
    derives hint-only candidates from the approved local catalogue. Require
    symbol, price, one-day, one-week and one-month percentage-change fields and
    source/retrieval timestamps. Test extra/missing fields, invalid numbers,
    duplicate symbols, stale source data, access denial and rate limits.
  - [ ] S13m-i: Add a versioned, deterministic reversal-hint filter after
    S13m-h. It must require the approved sign and threshold semantics for the
    seven-day and one-month percentage-change fields, price >$5, market cap
    >$100M, and current catalogue membership. Persist every rejection reason.
    Test boundary values and make clear that a hint cannot produce a plan or a
    Telegram notification without all downstream eligibility, evidence, analyst
    and risk checks.
  - [ ] S13m-j: Provide a documented, local-only input location for a manually
    supplied Ajaib US-stock response and an explicit import command. The command
    must validate the complete response and write a new immutable SQLite
    revision; it must make no network request. Test invalid/missing input and
    document that the ignored local file is not committed.
    Resume: `config/private_ajaib_us_stock.json` is the designated ignored
    location. The 2026-09-09 user-supplied 862-record response includes
    `price_1_day`, `price_1_week` and `price_1_month`; import it before adding
    any use of those fields. S13m-h/i remain required before it replaces FMP
    discovery or creates reversal hints.
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

D10 — Ajaib ranked-feed proposal: approve the exact data-access method and terms
before any adapter is built. Confirm whether the intended condition means
`PCT_CHANGE_1_WEEK < -3%` (rather than a raw price below $3), select the one-day
decline threshold/ranking depth, source-freshness limit, polling cadence and
rate budget. Approve whether this endpoint replaces FMP discovery or remains a
hint while FMP/Twelve Data independently recheck a shortlist. Without this
decision and authorized access, retain the existing FMP extreme-move-only path.

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

Current resume checkpoint (2026-09-08): S01–S08 complete and individually
committed. Git is initialized; earlier no-Git inventory above is historical.
Recent milestones: a0f7311 S03, 502216c S04, 4f63a4f S05, d7be45f S06,
1f88bd3 S07; use git log for the S08 commit containing this note. Fresh session:
run the listed verification commands, provision FMP_API_KEY and resume S09.
Outstanding non-credential decisions: D02 discovery thresholds/dedup/freshness,
D03 scheduling/reset budget, D06 valuation/exit parameters, D07 evidence/model
selection, and remaining D08 destination/expiry/retry settings. D04 has only a
hypothetical educational reference; D05 unavailable portfolio limits is approved.
