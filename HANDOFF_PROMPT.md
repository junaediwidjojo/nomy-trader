# Handoff — nomy-trader (continue with Claude or Cursor)

Copy the **Resume block** below into a new chat. Read `AGENTS.md` first; it is
binding for safety and engineering rules.

---

## Resume block (paste into new session)

You are continuing **nomy-trader**, an educational buy-side **research** repo
(not execution, not profitability claims). Remote: `github.com/junaediwidjojo/nomy-trader`
(`master`). Latest **pushed** commit: `ab2aa0b` — fail-closed JSON contract for
TradingAgents (no regex repair of markdown ratings).

**Pushed after intercept work:** see latest commit on `master` (intercept +
handoff). Local `var/` artifacts from verification runs are gitignored.

### What the app does today

1. Import / reuse Ajaib US-stock catalog in SQLite (`config/private_ajaib_us_stock.json`, gitignored).
2. Screen decline candidates (week/month drawdown, price, mcap filters).
3. **FMP `/profile` prescreen** (not `/quote` — account returns 402 on quote/EOD).
   Daily quota window ~250 calls; 8h reuse of persisted rows.
4. **TradingAgents** subprocess (`scripts/run_tradingagents_single.py`, separate
   venv at `../TradingAgents/.venv`) — baseline `gpt-oss-120b`, 1 debate round.
5. Optional high-model confirm (`qwen3p8-max`, 2 rounds) unless `--skip-confirm`.
6. Outputs under `var/` (gitignored): `screen_analyze_results.json`,
   `buy_candidates_latest.json`, `tradingagents_analysis_cache/` (48h TTL).

Telegram, broker, RAG, and automated exits are **out of scope** (ADR 005).

### AI-engineering milestone 1 — structured contract (plan 008)

**Goal:** Own `{rating, entry, stop, target, horizon, why}`. Fail closed on
`REVIEW`, markdown-only, or missing required fields. **Do not** regex-repair
`**Rating**` from prose.

**TradingAgents fact (read this before adding LLM calls):**

- Portfolio Manager and Trader already use `with_structured_output` → Pydantic.
- The graph **renders** that to markdown for reports; it does not expose JSON on stdout by default.
- **Correct approach:** Intercept `invoke_structured_or_freetext` on **each**
  agent module (they `from ... import invoke` at import time — patching only
  `structured.py` is insufficient). Capture PM + Trader `model_dump(mode="json")`,
  map in `decision_from_tradingagents()` in
  `src/nomy_trader/analysis/structured_decision.py`.
- **No second LLM** to “extract JSON from markdown” unless product explicitly
  reverses plan 008 deviation.

**Contract rules (local uncommitted behavior):**

| Field   | Source              | Required?                          |
|---------|---------------------|------------------------------------|
| rating  | Portfolio Manager   | yes (not `REVIEW`)                 |
| entry   | Trader `entry_price`| yes (positive number)              |
| stop    | Trader `stop_loss`  | yes (positive number)              |
| target  | PM `price_target`   | optional (null OK for Overweight)  |
| horizon | PM `time_horizon`   | yes                                |
| why     | PM summary/thesis   | yes                                |

If structured output fails → markdown fallback → `UNAVAILABLE` with reason.

**Key files:**

- `src/nomy_trader/analysis/structured_decision.py` — contract + map + accept
- `src/nomy_trader/analysis/pipeline.py` — `analyze_symbol()` → `SymbolAnalysis`
- `scripts/run_tradingagents_single.py` — capture + stdout JSON for pipeline
- `docs/plans/008-structured-analyst-contract.md`
- Tests: `tests/test_decision_parse.py`, `tests/test_analyze_pipeline.py`

### AMGN case study — why the intercept approach is “working”

AMGN did **not** become a buy signal in the last run. That is intentional and
shows the stack is doing the right thing.

**What we did (no extra LLM):**

1. Ran the full graph (`market` + `fundamentals`, `gpt-oss-120b`, 1 debate round).
2. **Before** Portfolio Manager markdown was written, the runner intercepted
   `invoke_structured_or_freetext` and saved typed JSON:
   - **Portfolio Manager:** `rating: Hold`, `time_horizon: 3-6 months`, rationale
     in `executive_summary`, `price_target: null`.
   - **Trader:** `action: Hold`, `entry_price: null`, `stop_loss: null`.
3. `decision_from_tradingagents()` merged those into our contract
   `{rating, entry, stop, target, horizon, why}`.
4. Pydantic validation **rejected** null `entry` / `stop` (required positives).
5. Pipeline surfaced **`UNAVAILABLE`** + `structured decision failed schema validation`
   — not Overweight/Hold parsed from prose, not invented $381 entry from markdown.

**Contrast NVO (happy path):** same intercept → PM **Overweight**, Trader
**entry 43.5 / stop 40.9**, PM **target 54** → accepted signal **Overweight**
with prices in the CLI table.

**Takeaway:** “Works well” for AMGN means **trustworthy refusal** when the
agents do not supply quotable levels. To get an actionable AMGN row you need
either a TA run where Trader fills `entry_price` and `stop_loss`, or an explicit
product change to allow rating-only Hold (not implemented; would weaken fail-closed).

Inspect proof in cache file `AMGN_*_<profile_key>.json` → `runner_payload`:
`structured_source: tradingagents_structured`, `tradingagents_structured.trader`.

### Last live verification (local `var/`, not in git)

Command:

```sh
cd /path/to/nomy-trader
.venv/bin/python -u -m nomy_trader analyze \
  --symbols BRZE NVO AMGN \
  --skip-catalog-import --skip-confirm --force-reanalyze \
  --timeout 420 \
  --output var/structured_intercept_brze_nvo_amgn.json
```

Results (~5 min, 2 symbols analyzed):

| Symbol | FMP / TA | Outcome |
|--------|----------|---------|
| BRZE   | FMP reject `already_rebounded_above_3_percent` | never ran TA |
| NVO    | Intercept OK | **Overweight**, entry 43.5, stop 40.9, target 54 |
| AMGN   | Intercept OK, Trader Hold with null entry/stop | **UNAVAILABLE** (schema — fail closed) |

Artifact: `var/structured_intercept_brze_nvo_amgn.json`. Inspect cache payloads:
`tradingagents_structured.portfolio_manager` / `.trader`, field
`structured_source`: `tradingagents_structured`.

### Ops commands

```sh
# Daily cheap scan (reuse catalog)
.venv/bin/python -u -m nomy_trader run --top 50 --skip-confirm --skip-catalog-import

# Explicit symbols, no high-model confirm
.venv/bin/python -u -m nomy_trader analyze --symbols ASM AMGN --skip-catalog-import --output var/my_run.json

# Burn cache / spend Fireworks again
--force-reanalyze
```

**Pitfalls:**

- Do not `nohup` long TA jobs without keeping shell alive; use foreground `python -u` + `tee`.
- Piping through `grep` can empty logs.
- `--force-reanalyze` on confirm runs can overwrite `var/buy_candidates_latest.json`.
- FMP prescreen pool: `top * PRESCREEN_POOL_MULTIPLIER` (2).
- TradingAgents python: `../TradingAgents/.venv/bin/python` or `TRADINGAGENTS_PYTHON`.

### Agreed next (not implemented)

1. **Commit + push** intercept work after user approves; link plan 008.
2. **Milestone 2 — grounding:** inject FMP profile + Ajaib prints into confirm
   prompt so high model cannot claim “no quote in debate.”
3. **Eval set:** AMGN, CRS, KGC, ARQQ, FMC — agreement, empty reports, cost.
4. **Product TBD:** Should **Hold** with null Trader prices be accepted (rating
   only, no entry/stop) or stay fail-closed? Current code requires entry+stop.

### Verification checklist for any change

- `PYTHONPATH=. .venv/bin/pytest` (190 tests; some need PYTHONPATH for `tests.*` imports)
- `.venv/bin/ruff check .` and format
- `.venv/bin/mypy src` (known pre-existing errors in `__main__.py`, ajaib — not introduced by 008)
- State what was **not** verified (live Fireworks spend).

### Secrets and portfolio safety

- `.env` and `config/private*` are gitignored; never print `.env` values.
- `var/` gitignored. Public repo has MIT LICENSE, secret scanning enabled.

---

## Historical note

Older text in this file referred to Telegram-first MVP and IBKR; that path is
archived. Active experiment path is documented in root `README.md` and plan 007.
