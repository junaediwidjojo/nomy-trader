# nomy-trader

Educational research tool for **possible overreactions after stock declines**.
It screens Ajaib US-stock snapshots, applies cheap deterministic gates, then
optionally asks TradingAgents for a supplementary signal. You execute
elsewhere. There is **no broker integration**, order submission, position
tracking, or claim of profitability. Stops and targets are commentary only.

## Current experiment (Sep 2026)

The working loop is no longer “FMP biggest losers → Telegram recommendation.”
It is a **cost-aware screen-and-review pipeline**:

1. Fetch or import an Ajaib US-stock JSON snapshot.
2. Rank **week-weighted drawdowns** (AMGN-like: large weekly drop that has
   already stopped crashing today).
3. **FMP `/profile` prescreen** (this account’s quote/history endpoints return
   HTTP 402). Reject ETFs/funds, thin dollar volume, Ajaib–FMP price mismatch,
   and names already rebounded more than +3% today. Observations reuse for 8h
   so repeat runs do not burn the 250/day FMP budget.
4. Run TradingAgents on the top N with **gpt-oss-120b, 1 debate round**
   (baseline). Cache hits skip the model for 48h per symbol+profile.
5. **High-model re-verify** (`qwen3p8-max`, 2 rounds) only when you want it:
   Buy/Overweight, or a Hold whose parsed target is ≥5% above the live FMP
   price. Use `--skip-confirm` to stay on the cheap model.

### What we observed

| Pass | Result |
|------|--------|
| Tight 1d/1w crash filters | 0 Buys; mostly Hold/Underweight; Fireworks spend on names still falling |
| Wider funnel + FMP live 1d ≤ −1% | Rejected names that had already bounced (the AMGN pattern) |
| Week-weighted rank + skip high model | Top 50 on 15 Sep: **ASM, AMGN, CRS, KGC Overweight**; plus Hold upside on NVS, SMR, SNDK, AGCO |
| High-model confirm on those 4 Overweights | **All disputed** (Hold or unparsed REVIEW). None confirmed |
| High-model BRZE / NVO | Both **Hold**, and often **no price levels** because the debate lacked quotes |

Baseline is cheap and noisy. High model is expensive and conservative. Treat
Overweight as a **research shortlist**, not a buy.

### Cheap filters worth keeping

- Prefer **weekly drawdown**, not same-day crash ranking (ARQQ-style −18% 1d
  names came back Underweight).
- Keep names whose **live 1d is roughly −5% to +2%**, price **>$20**, and FMP
  dollar volume **≥ $5M**.
- Do **not** require a fresh 1d decline on FMP; that deleted AMGN-like setups.
- Spend Fireworks on **re-verify of Overweight / material-upside Holds**, not
  on the full Ajaib list.

## Run

Needs Python 3.12+, a local `.venv` or `uv`, `FMP_API_KEY`, `AJAIB_COOKIE` for
fetch, and Fireworks via TradingAgents’ sibling checkout (see
[`config/README.md`](config/README.md)). Never commit `.env` or
`config/private_*`.

```sh
# Fresh Ajaib list, screen, baseline TradingAgents on top 50, no high-model pass
.venv/bin/python -u -m nomy_trader run --fetch-catalog --top 50 --skip-confirm

# Resume later: reuse TradingAgents cache (48h) and FMP rows (8h)
.venv/bin/python -u -m nomy_trader run --top 50 --skip-confirm --skip-catalog-import

# High-model re-verify of named Overweights (writes a separate JSON)
.venv/bin/python -u -m nomy_trader analyze --symbols ASM AMGN CRS KGC \
  --skip-catalog-import --output var/confirm_overweight_results.json
```

Do not pass `--force-reanalyze` unless you intend to spend Fireworks again.

Artifacts (gitignored): `var/screen_analyze_results.json`,
`var/buy_candidates_latest.json`, `var/tradingagents_analysis_cache/`.

## Safety

- TradingAgents output is untrusted supplementary text.
- An LLM must not size positions, bypass policy, or talk to a broker.
- Missing data blocks a buy **notification** in the original MVP design; this
  sandbox does not send Telegram and does not execute.

## Offline checks

```sh
uv sync --locked
uv run ruff format --check .
uv run ruff check .
uv run mypy src
uv run pytest
```

Older FMP discovery, Twelve Data recheck, Massive EOD, and the manual large-cap
seed list still exist in the repo; they are **not** the daily experiment path.
Telegram and broker automation remain out of scope (ADR 005).

Plans: [007 screen-analyze](docs/plans/007-ajaib-screen-analyze-mvp.md),
[006 TradingAgents](docs/plans/006-tradingagents-integration.md). Product and
policy: `docs/PRODUCT_SPEC.md`, `docs/TRADING_POLICY.md`, `AGENTS.md`.

## AI-engineering learning (next)

The current LLM use is a **subprocess black box**: we set env vars, wait, parse
`**Rating**` from markdown. That is a start, not an AI-engineer stack. Useful
next practice, in order:

1. **Structured outputs** — JSON schema for rating / entry / stop / target;
   reject instead of regex-repairing `REVIEW`.
2. **Grounding** — inject FMP profile + Ajaib prints into the prompt so high
   model cannot claim “no quote in this debate.”
3. **Eval set** — freeze a dated shortlist (AMGN, CRS, KGC, ARQQ, FMC) and
   score baseline vs confirm for agreement, empty reports, and cost per call.
4. **Tool use you own** — a small agent that may call FMP profile / history
   only, with quota, timeouts, and logged traces (LangSmith or local JSONL).
5. **Not yet** — RAG over filings (see [ADR 003](docs/decisions/003-no-rag-initially.md)),
   Telegram, or any broker path.
