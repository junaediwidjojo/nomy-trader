# Local configuration inputs

Save the newest user-exported Ajaib US-stock response as:

`config/private_ajaib_us_stock.json`

This path is ignored by Git because it may contain private account or catalogue
data. The file must be the complete JSON response, including `err_message`,
`result.count`, and `result.results`; do not paste only a table or selected
symbols.

The application validates the approved status and count before storing an
immutable local SQLite snapshot. A supplied snapshot is a discovery hint and
availability reference. It does not prove that an order is possible in Ajaib,
that a security is a common stock, or that it is suitable to buy.

Import a newly saved response with:

```text
uv run python -m nomy_trader ajaib-import
```

Create the local, non-trading research shortlist from the latest imported
snapshot with:

```text
uv run python -m nomy_trader ajaib-hints
```

For the read-only SEC EDGAR filing-metadata provider, add a contact User-Agent
to the local `.env` before running any future filing lookup:

```text
SEC_USER_AGENT="nomy-trader your-email@example.com"
```

This is not an SEC account, API key, broker credential or trading permission.

## TradingAgents sandbox

TradingAgents is a separate comparison tool, not part of nomy-trader's decision,
risk, plan or notification pipeline. To use a Fireworks trial key through its
OpenAI-compatible endpoint, add these local `.env` values:

```text
OPENAI_COMPATIBLE_API_KEY="paste-your-Fireworks-key-here"
TRADINGAGENTS_LLM_PROVIDER="openai_compatible"
TRADINGAGENTS_LLM_BACKEND_URL="https://api.fireworks.ai/inference/v1"
TRADINGAGENTS_DEEP_THINK_LLM="accounts/fireworks/models/gpt-oss-120b"
TRADINGAGENTS_QUICK_THINK_LLM="accounts/fireworks/models/gpt-oss-120b"
TRADINGAGENTS_MAX_DEBATE_ROUNDS="1"
TRADINGAGENTS_MAX_RISK_ROUNDS="1"
TRADINGAGENTS_CHECKPOINT_ENABLED="false"
TRADINGAGENTS_MAX_TOKENS="2400"
```

Do not put the Fireworks key in Git, source code, logs, a Telegram message, or
the dedicated TradingAgents checkout. `gpt-oss-120b` was verified available to
the current Fireworks account and produces structured tool calls. The prior
`glm-5p3-flash` experiment returned empty content after tool results. The
2,400-token cap allows report text after reasoning tokens. The integration must
still verify a bounded sandbox run before it accepts output as supplementary
research.

The application exposes a `TradingAgentsSubprocessAdapter`, but it has no
default command. A future local runner must receive a JSON request on standard
input and return exactly this JSON shape on standard output:

```json
{"status":"SUPPORTS","summary":"Cited commentary.","evidence_ids":["evidence-id"]}
```

The status may instead be `CHALLENGES`. The adapter sets the process timeout,
hashes the accepted response, verifies every evidence ID against the curated
packet, and changes any failure to an unavailable review. Do not point this
adapter at TradingAgents' raw graph until its Yahoo Finance fallback timeout is
fixed; the raw graph may make provider requests outside the curated-facts
boundary.

## Ajaib US-stock fetch (optional automation)

The screener endpoint used by the Ajaib web app is:

`https://ajaib.co.id/api/us-stock?page_size=10000&filter_type=&sort_type=PCT_CHANGE_1_DAY&sort_direction=DESC`

There is **no public documented API** for this US-stock list. Ajaib's published
developer API is for **crypto exchange** only. The web endpoint is protected by
Cloudflare; in practice a **browser cookie jar** (often without login) is enough.
The important piece is usually `__cf_bm`, which expires quickly (~30 minutes).

To automate fetches, copy session headers once from Chrome DevTools:

1. Log in at [ajaib.co.id](https://ajaib.co.id) and open the US-stock screener.
2. Open DevTools → Network, reload, filter `us-stock`.
3. Open the request → copy **Request Headers**:
   - `Cookie` (include `cf_clearance` if present)
   - `Authorization` if present (some builds send `Bearer ...`)
4. Put them in local `.env` (never commit):

```text
AJAIB_COOKIE="paste-cookie-header-here"
# optional:
AJAIB_AUTHORIZATION="Bearer ..."
```

Then fetch to the usual JSON path:

```sh
uv run python -m nomy_trader ajaib-fetch
```

Or combine fetch + full pipeline:

```sh
uv run python -m nomy_trader run --fetch-catalog
```

Cookies expire; refresh `AJAIB_COOKIE` when fetch returns a Cloudflare error.

## Daily one-command run

After updating Ajaib data (fetch or manual paste into
`config/private_ajaib_us_stock.json`), run:

```sh
cd /Users/junaediwidjojo/HobbyProjects/nomy-trader
uv run python -m nomy_trader run --fetch-catalog
```

That single command:

1. Imports the Ajaib snapshot (with `--fetch-catalog`)
2. Screens decline candidates (price, market cap, 1d/1w loss filters)
3. Runs TradingAgents on the **top 12** ranked survivors (change with `--top N`)
4. Auto-runs high-model confirmation when primary signal is Buy/Overweight
5. Prints signals, buy summary, and price hints
6. Writes `var/screen_analyze_results.json`
7. Writes `var/buy_candidates_latest.json` (learning file for bullish names)
8. Writes `var/latest_run_stamp.txt` (run metadata for the next session)

Wider learning scan while Fireworks credits are available:

```sh
uv run python -m nomy_trader run --fetch-catalog --top 20
```

Use **`CONFIRMED_BULLISH`** as the actionable shortlist; treat **`DISPUTED_BULLISH`**
(primary Buy/Overweight but confirmation disagrees) as reject for now.

Production TradingAgents profile (locked in code as `baseline`):

- Primary: `TRADINGAGENTS_MAX_DEBATE_ROUNDS=1`, `gpt-oss-120b`
- If primary signal is **Buy** or **Overweight**, a confirmation pass runs with
  `high_model_two_round_debate` (Qwen3.8 Max, 2 debate rounds, 900s timeout)

TradingAgents results are cached locally for 48 hours per symbol and profile
under `var/tradingagents_analysis_cache/`. A repeat `run` skips live AI calls
for symbols analyzed within that window.

Optional flags:

```sh
uv run python -m nomy_trader run --top 6
uv run python -m nomy_trader run --skip-catalog-import   # reuse last SQLite import
uv run python -m nomy_trader run --force-reanalyze       # ignore cache
uv run python -m nomy_trader compare-profiles --symbol NVO  # sandbox experiments only
```

Override cache TTL with `TRADINGAGENTS_CACHE_TTL_HOURS` (default: `48`).

## Running TradingAgents from nomy-trader

TradingAgents stays in its own checkout and virtual environment. Never run its
batch script with nomy-trader's `.venv`.

The Yahoo Finance fundamentals call is bounded by
`YFINANCE_REQUEST_TIMEOUT_SECONDS` (default: `20`). A timeout becomes an
unavailable fundamentals result for that symbol; it does not make the batch
wait indefinitely.

Run a small ranked batch, beginning with one to four symbols:

```sh
export PATH="/private/tmp/nomy-tooling/bin:$PATH"

cd /Users/junaediwidjojo/HobbyProjects/nomy-trader
set -a && source .env && set +a
export YFINANCE_REQUEST_TIMEOUT_SECONDS=20

cd /Users/junaediwidjojo/HobbyProjects/TradingAgents
uv run python ../nomy-trader/scripts/run_tradingagents_batch.py BRZE AHCO XE CHWY
```

On this host, if `uv` is unavailable, use TradingAgents' own interpreter while
keeping the rest of the command unchanged:

```sh
/Users/junaediwidjojo/HobbyProjects/TradingAgents/.venv/bin/python \
  ../nomy-trader/scripts/run_tradingagents_batch.py BRZE
```

The script writes a compact batch status to
`nomy-trader/var/tradingagents_batch_results.json` and complete reports under
`~/.tradingagents/logs/nomy-trader-session/reports/`. Both paths are local and
ignored by Git. Treat reports as supplementary, untrusted commentary; only
primary evidence and deterministic checks can promote a signal.
