# Ajaib screen-and-analyze MVP ExecPlan

Status: approved for implementation 2026-09-11 by user request.
Telegram delivery, broker execution, and full evidence-packet integration are
explicitly out of scope for this milestone.

## 1. Goal and user-visible outcome

One command chain:

1. User supplies an Ajaib US-stock JSON snapshot (`ajaib-import`).
2. Program filters decline candidates (price, market cap, 1d/1w loss thresholds).
3. Program runs TradingAgents on the top N survivors (or explicit symbols).
4. Program prints a table and saves JSON with signal, price target, and entry
   hints extracted from TradingAgents commentary.

Example (one command):

```sh
uv run python -m nomy_trader run
```

Equivalent:

```sh
uv run python -m nomy_trader analyze --top 4
```

Both import `config/private_ajaib_us_stock.json` by default, screen decline
candidates, run TradingAgents on the top four, and write
`var/screen_analyze_results.json` plus `var/latest_run_stamp.txt`.

The production profile is locked to one debate round and
`accounts/fireworks/models/gpt-oss-120b` via `default_run_env_overrides()`.
Use `compare-profiles` only for sandbox experiments.

## 2. Scope and non-goals

**In scope:** hint screening reuse, subprocess TradingAgents runner, decision
parsing, `analyze` CLI, JSON artifact at `var/screen_analyze_results.json`.

**Out of scope:** Telegram, broker orders, SQLite review persistence, curated
evidence-packet adapter (plan 006), deterministic position sizing, profitability
claims.

## 3. Safety invariants

- TradingAgents output is supplementary and untrusted.
- Price targets and entry hints are model commentary, not execution instructions.
- Runner uses TradingAgents' separate venv; nomy-trader does not import the graph.
- Per-symbol timeout defaults to 180 s; failures become per-symbol errors.
- Analyst scope remains `market` + `fundamentals` only.

## 4. Implementation

| Piece | Path |
|-------|------|
| Decision parser | `src/nomy_trader/analysis/decision_parse.py` |
| Pipeline | `src/nomy_trader/analysis/pipeline.py` |
| Single-symbol runner | `scripts/run_tradingagents_single.py` |
| CLI | `analyze` in `src/nomy_trader/__main__.py` |

## 5. Follow-on (not this milestone)

- Wire plan 006 curated adapter for signal-pipeline `SUPPORTS`/`CHALLENGES`.
- Persist runs to SQLite journal.
- Fresh live quote gate before recommending entry.
