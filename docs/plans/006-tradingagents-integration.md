# TradingAgents integration ExecPlan

Status: proposed for user approval 2026-09-11.
Supersedes ad-hoc batch invocation in S17c only for the integration path;
broker execution, order submission, and Telegram delivery remain excluded.

## 1. Goal and user-visible outcome

Wire nomy-trader's existing `TradingAgentsSubprocessAdapter` to a locally
configured TradingAgents runner so that a curated `EvidencePacket` can receive
a bounded `TradingAgentsReview` (`SUPPORTS`, `CHALLENGES`, or `UNAVAILABLE`)
without importing TradingAgents into nomy-trader's virtual environment.

User-visible outcomes:

- `uv run python -m nomy_trader tradingagents-review --symbol FIZZ` runs one
  bounded review for a symbol that already has a curated evidence packet.
- `uv run python -m nomy_trader tradingagents-batch --from-hints --top 4`
  runs reviews for the top N Ajaib hint survivors (optional convenience).
- Raw TradingAgents reports remain in `~/.tradingagents/logs/` and
  `var/tradingagents_batch_results.json` as supplementary, untrusted artifacts.
- The signal pipeline (`compose_signal_outcome`) can consume a validated review;
  `CHALLENGES` or `UNAVAILABLE` downgrades to `WATCH`, never auto-promotes.

## 2. Scope and explicit non-goals

**Scope**

- A thin subprocess runner script (in nomy-trader `scripts/`) that:
  - reads `CuratedTradingAgentsRequest` JSON from stdin,
  - invokes TradingAgents in its separate venv via subprocess,
  - maps graph output to the strict `_RunnerResponse` contract on stdout.
- CLI commands to invoke the adapter for one symbol or a hints-driven batch.
- Environment configuration for runner path, timeout, and TradingAgents `.env`
  passthrough documented in `config/README.md`.
- Tests for runner mapping, timeout, malformed output, and evidence-ID validation.

**Non-goals**

- Installing TradingAgents dependencies into nomy-trader's `.venv`.
- In-process `TradingAgentsGraph` import inside nomy-trader application code.
- Passing raw webpage/filing text across the curated-facts boundary.
- Letting TradingAgents set entry price, position size, stop, target, or final
  `SignalOutcome`.
- Enabling social/Reddit, FRED, or Polymarket analysts until deliberately
  configured and bounded.
- SQLite persistence of full TradingAgents reports (hash + summary only in
  `TradingAgentsReview`).
- Broker integration or automated order submission.

## 3. Relevant existing modules and specifications

| Module | Role |
|--------|------|
| `src/nomy_trader/providers/tradingagents.py` | `CuratedTradingAgentsRequest`, `TradingAgentsSubprocessAdapter`, `_RunnerResponse` |
| `src/nomy_trader/signals.py` | `TradingAgentsReview`, `validate_tradingagents_review`, `compose_signal_outcome` |
| `scripts/run_tradingagents_batch.py` | Ad-hoc in-process batch; bypasses adapter boundary |
| `config/README.md` | TradingAgents sandbox env vars, invocation, Yahoo timeout |
| `tests/test_tradingagents_adapter.py` | Adapter contract tests |
| `docs/plans/004-generic-price-signal-workflow.md` | Pipeline position of `TradingAgentsReview` |
| `docs/plans/001-mvp-scope-revision.md` S17b/S17c | Sandbox comparison milestone context |
| TradingAgents checkout | `TradingAgentsGraph.propagate()`, `yf_with_timeout`, `selected_analysts` |

**Current gap**

```
ajaib-hints ──► (manual) ──► run_tradingagents_batch.py
                              │
                              ▼ in-process propagate()
                    var/tradingagents_batch_results.json

EvidencePacket ──► TradingAgentsSubprocessAdapter ──► ??? (no default runner)
```

The batch script calls `propagate(ticker, trade_date)` directly with no curated
packet, no evidence-ID citations, and no `_RunnerResponse` mapping. The
application adapter is production-ready but has no runner to call.

## 4. Proposed design and alternatives considered

### Recommended: subprocess runner bridge (hybrid)

```
EvidencePacket
  │ curated_request()
  ▼
CuratedTradingAgentsRequest (JSON stdin)
  │
  ▼
scripts/run_tradingagents_curated_runner.py  ← NEW
  │ subprocess: TradingAgents/.venv/bin/python
  │ selected_analysts=("market", "fundamentals")
  │ env: TRADINGAGENTS_*, YFINANCE_REQUEST_TIMEOUT_SECONDS
  ▼
propagate() → map to _RunnerResponse (JSON stdout)
  │
  ▼
TradingAgentsSubprocessAdapter.review() → TradingAgentsReview
```

The runner is a **separate process** launched by the adapter (or CLI). It does
not import TradingAgents into nomy-trader. Internally it may either:

1. **Delegate** to a one-liner subprocess of TradingAgents' own interpreter
   (preferred isolation), or
2. **Import** TradingAgents only inside the runner script when executed under
   TradingAgents' venv (simpler, matches current batch script pattern).

Keep `run_tradingagents_batch.py` as a **research sandbox** for exploratory
multi-symbol runs that do not feed the signal pipeline. Optionally refactor it
to share the runner's `run_symbol()` helper.

### Alternatives considered

| Alternative | Verdict |
|-------------|---------|
| **In-process module** — `import tradingagents` inside nomy-trader | Rejected: couples venvs, violates isolation documented in `config/README.md`, increases dependency surface |
| **Direct adapter → batch script** — point adapter at batch script | Rejected: batch script ignores stdin curated packet and returns wrong JSON shape |
| **Extend contract** — add `raw_signal`, `report_path` to `TradingAgentsReview` | Deferred: pollutes the pure signal contract; keep sandbox artifacts external |
| **LLM synthesis step** — ask Fireworks to map report → SUPPORTS/CHALLENGES with citations | Rejected for MVP: adds second model call, citation reliability risk; prefer deterministic keyword/heuristic mapper first |
| **Drop TradingAgents from pipeline** — sandbox only, manual comparison | Rejected: S17c and plan 004 require adapter integration |

### Yahoo Finance timeout mitigation

Already implemented in TradingAgents checkout (`yf_with_timeout`, default 20 s
via `YFINANCE_REQUEST_TIMEOUT_SECONDS`). The 2026-09-11 batch (4 symbols,
~2.6 min each) completed without hangs, confirming the fix.

Residual risks and mitigations:

| Risk | Mitigation |
|------|------------|
| `Ticker.info` stall | `yf_with_timeout` daemon-thread guard (done) |
| OHLCV history hang | `stockstats_utils.yf_retry` + timeout path |
| Reddit 429 backoff (71 s) | Keep `selected_analysts=("market", "fundamentals")` only |
| LangGraph node stall (non-Yahoo) | Add per-symbol wall-clock timeout in runner (e.g. 180 s); kill subprocess → `UNAVAILABLE` |
| Fireworks empty content | `TRADINGAGENTS_MAX_TOKENS=2400`, `gpt-oss-120b` (verified) |

The runner must set `YFINANCE_REQUEST_TIMEOUT_SECONDS` and enforce an overall
`subprocess` timeout independent of Yahoo's per-request guard.

## 5. Data-model or API changes

### No change to `TradingAgentsReview` contract

Keep the frozen contract:

```python
status: SUPPORTS | CHALLENGES | UNAVAILABLE
summary: str  # cited commentary, no price/size/action
report_hash: str  # SHA-256 of runner stdout
evidence_ids: tuple  # subset of packet evidence IDs
```

### New runner stdout contract (already defined as `_RunnerResponse`)

```json
{"status":"SUPPORTS","summary":"...","evidence_ids":["filing-8k"]}
```

### New environment variables

| Variable | Purpose | Default |
|----------|---------|---------|
| `TRADINGAGENTS_RUNNER_COMMAND` | Adapter subprocess command | `TradingAgents/.venv/bin/python scripts/run_tradingagents_curated_runner.py` |
| `TRADINGAGENTS_RUNNER_TIMEOUT_SECONDS` | Adapter wall-clock timeout | `180` |
| `TRADINGAGENTS_PYTHON` | Interpreter path for runner | sibling checkout `.venv/bin/python` |
| Existing `TRADINGAGENTS_*`, `OPENAI_COMPATIBLE_API_KEY` | Passed through to runner child env | per `config/README.md` |
| `YFINANCE_REQUEST_TIMEOUT_SECONDS` | Per-request Yahoo guard | `20` |

### Mapping `propagate()` output → `_RunnerResponse`

`propagate()` returns `(final_state, signal)` where `signal` is a portfolio
action string (`Hold`, `Underweight`, `Sell`, `Buy`, etc.) and `final_state`
contains `market_report`, `fundamentals_report`, `final_trade_decision`.

**Proposed deterministic mapper (v1, no extra LLM call):**

| TradingAgents signal | Mapper status | Rationale |
|---------------------|---------------|-----------|
| `Sell`, `Underweight` | `CHALLENGES` | Bearish relative to buy-the-dip thesis |
| `Buy`, `Overweight` | `SUPPORTS` | Bullish |
| `Hold` | `SUPPORTS` if curated observations show no active business-risk block; else `CHALLENGES` | Hold is neutral-to-negative for a decline candidate |
| Missing/empty reports | `UNAVAILABLE` | No usable commentary |
| Timeout / exception | `UNAVAILABLE` | Adapter already handles |

**Summary construction:** Extract first paragraph of `final_trade_decision`
(executive summary), prefix with `[TradingAgents sandbox]`, truncate to 500 chars.
Append `(signal={signal})` for traceability. Do **not** include price targets or
position-sizing language in the summary passed to the adapter (strip via regex
or omit `final_decision` fields that match `Price Target`, `stop`, `trim`).

**Evidence IDs:** Runner receives curated packet evidence IDs on stdin. v1 cites
**all primary evidence IDs** from the packet (conservative). v2 (TBD) may parse
report text for explicit evidence references.

### CLI command design

```
uv run python -m nomy_trader tradingagents-review --symbol FIZZ [--timeout 180]
uv run python -m nomy_trader tradingagents-batch --symbols FIZZ ADBE [--timeout 180]
uv run python -m nomy_trader tradingagents-batch --from-hints --top 4
```

Behavior:

- `tradingagents-review` loads or builds an `EvidencePacket` for the symbol
  (from fixture file initially; from SQLite journal in a later milestone),
  calls `TradingAgentsSubprocessAdapter.review()`, prints JSON result.
- `tradingagents-batch` loops symbols sequentially (no parallel — quota/credit
  control), writes `var/tradingagents_batch_results.json` with per-symbol
  adapter results plus optional sandbox metadata.
- `--from-hints` reuses `run_reversal_hint_scan()` top N survivors.

## 6. Safety invariants and failure behavior

Per `AGENTS.md` and plan 004:

- **Curated facts boundary:** Only `CuratedTradingAgentsRequest` crosses stdin.
  No `content_or_licensed_reference`, URLs, or raw filing bodies.
- **No broker:** Runner and CLI produce reviews only; no order fields.
- **Token caps:** `TRADINGAGENTS_MAX_TOKENS=2400`, `MAX_DEBATE_ROUNDS=1`,
  `MAX_RISK_ROUNDS=1`, `CHECKPOINT_ENABLED=false`.
- **Untrusted output:** Reports are supplementary; mapper output is validated
  against `_RunnerResponse` schema. Malformed stdout → `UNAVAILABLE`.
- **Evidence verification:** `evidence_ids` must be subset of packet IDs;
  adapter already enforces this.
- **No silent pass:** `UNAVAILABLE` → `WATCH` with reason
  `tradingagents_review_unavailable`; `CHALLENGES` → `WATCH` with
  `tradingagents_challenges_thesis`.
- **Timeout:** Subprocess kill → `UNAVAILABLE`; no partial acceptance.
- **Credentials:** Fireworks key stays in `.env`; never logged, committed, or
  sent via Telegram.
- **Analyst scope:** `selected_analysts=("market", "fundamentals")` only until
  Reddit/FRED/Polymarket are deliberately bounded.

## 7. Ordered implementation steps

### M1 — Curated runner script (foundation)

1. Create `scripts/run_tradingagents_curated_runner.py`:
   - Read `CuratedTradingAgentsRequest` from stdin.
   - Load `.env` from nomy-trader root (same pattern as batch script).
   - Invoke `TradingAgentsGraph` with bounded config.
   - Apply signal→status mapper; emit `_RunnerResponse` JSON on stdout.
   - On any failure, emit nothing (non-zero exit) so adapter returns
     `UNAVAILABLE`.
2. Add focused unit tests for mapper logic (pure functions, no network).
3. Manual smoke test: pipe a fixture `CuratedTradingAgentsRequest` for FIZZ.

**Verification:** Runner stdout validates against `_RunnerResponse`; exit 0
within 180 s for FIZZ.

### M2 — Wire adapter default command

1. Add `TRADINGAGENTS_RUNNER_COMMAND` and `TRADINGAGENTS_RUNNER_TIMEOUT_SECONDS`
   to settings loading (`.env` / `load_dotenv`).
2. Factory function `build_tradingagents_adapter()` that reads env and returns
   `TradingAgentsSubprocessAdapter` or `None` if unconfigured.
3. Integration test with mocked subprocess returning valid JSON.

**Verification:** `test_tradingagents_adapter.py` passes; new test covers env-based
construction.

### M3 — CLI commands

1. Add `tradingagents-review` and `tradingagents-batch` to `__main__.py`.
2. `tradingagents-review` uses fixture packet (or `--packet` JSON path) until
   evidence-packet builder exists.
3. `tradingagents-batch --from-hints` integrates with `ajaib_hints`.

**Verification:** CLI prints valid `TradingAgentsReview` JSON for one symbol.

### M4 — Refactor batch script (optional cleanup)

1. Extract shared `run_symbol()` + config builder into
   `scripts/tradingagents_common.py`.
2. Batch script calls shared helper; runner calls same helper internally.
3. Update `config/README.md` with runner invocation.

**Verification:** Existing batch invocation still works; results unchanged.

### M5 — Evidence-packet integration (depends on S17c evidence builder)

1. Replace fixture packet with SQLite-backed `EvidencePacket` per symbol.
2. Runner cites actual primary evidence IDs from packet.
3. Persist `TradingAgentsReview` (hash + summary) to journal table.

**Verification:** End-to-end `ajaib-hints → evidence → tradingagents-review →
compose_signal_outcome` for one symbol.

## 8. Test and validation plan

| Test | Type | Covers |
|------|------|--------|
| Mapper: Sell → CHALLENGES | unit | signal mapping |
| Mapper: Hold + no risk block → SUPPORTS | unit | neutral case |
| Mapper: empty reports → UNAVAILABLE | unit | failure path |
| Runner: valid stdin → valid stdout schema | integration (mocked graph) | contract |
| Adapter: timeout → UNAVAILABLE | unit (existing) | timeout |
| Adapter: bad evidence_ids → UNAVAILABLE | unit (existing) | citation guard |
| CLI: tradingagents-review --symbol FIZZ | manual | smoke (1 symbol, <3 min) |
| CLI: tradingagents-batch --from-hints --top 4 | manual | batch (today's run) |
| Yahoo timeout: YFINANCE_REQUEST_TIMEOUT_SECONDS=1 on slow symbol | manual | hang prevention |

Before merge: `uv run ruff check`, `uv run mypy`, `uv run pytest`.

## 9. Rollback or recovery approach

- Runner is additive; removing `TRADINGAGENTS_RUNNER_COMMAND` disables the
  adapter (all reviews → `UNAVAILABLE` → `WATCH`). No pipeline regression.
- Batch script remains usable independently for sandbox research.
- TradingAgents checkout changes (Yahoo timeout) are in the sibling repo;
  nomy-trader rollback does not affect them.
- If Fireworks credits exhaust mid-batch, partial results in
  `var/tradingagents_batch_results.json` are preserved; rerun skips completed
  symbols via `--skip-existing` (TBD convenience flag).

## 10. Open decisions requiring user approval

| ID | Decision | Options | Recommendation |
|----|----------|---------|----------------|
| TBD-1 | **Hold → SUPPORTS or CHALLENGES?** | (a) Always CHALLENGES for decline thesis (b) Context-dependent on business gate (c) Always SUPPORTS (neutral) | **(b)** — context-dependent; Hold blocks `MANUAL_BUY_CANDIDATE` via `WATCH` when combined with unavailable market data |
| TBD-2 | **Evidence citation strategy v1** | (a) Cite all primary IDs (b) Cite none → always UNAVAILABLE (c) LLM extraction | **(a)** for MVP |
| TBD-3 | **Per-symbol timeout** | 120 s / 180 s / 300 s | **180 s** (2026-09-11 runs ~160 s/symbol) |
| TBD-4 | **Persist reviews to SQLite now or later?** | M3 vs M5 | **M5** — after evidence packet builder |
| TBD-5 | **Strip price/sizing from summary?** | Regex strip vs include with disclaimer | **Strip** — contract forbids price/size/action fields |
| TBD-6 | **Parallel batch execution?** | Sequential vs parallel | **Sequential** — credit control, simpler timeout |
| TBD-7 | **Approve M1 implementation?** | Proceed / revise plan | User approval required per `AGENTS.md` |
