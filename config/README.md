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
