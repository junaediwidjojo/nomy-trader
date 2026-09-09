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
