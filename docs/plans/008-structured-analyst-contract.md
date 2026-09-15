# Structured analyst decision contract

Status: approved for implementation 2026-09-15 by user request (AI-engineering
milestone 1: own the contract).

## 1. Goal and user-visible outcome

nomy-trader accepts a TradingAgents review only when the runner supplies a JSON
object matching `{rating, entry, stop, target, horizon, why}`. `REVIEW`,
missing quotes, or prose-only markdown fail closed. The pipeline does not
regex-repair `**Rating**` or invent prices.

CLI rows show `UNAVAILABLE` plus a rejection reason instead of a guessed Hold.

## 2. Scope and non-goals

**In scope**

- Pydantic contract in nomy-trader.
- JSON-only accept path in `analyze_symbol`.
- One extra OpenAI-compatible completion in `run_tradingagents_single.py` that
  must emit that JSON (schema / `json_object`). No field coercion.
- Tests for accept, REVIEW, empty quotes, markdown-only, malformed JSON.

**Non-goals**

- Changing TradingAgents' Portfolio Manager schema or markdown renderer.
- Grounding FMP/Ajaib into the confirm prompt (milestone 2).
- Eval harness, owned tools, RAG, Telegram, broker.

## 3. Relevant modules

- `src/nomy_trader/analysis/structured_decision.py` (new)
- `src/nomy_trader/analysis/pipeline.py` (`analyze_symbol`)
- `scripts/run_tradingagents_single.py`
- Replaces regex `decision_parse.py`

## 4. Design

TradingAgents still produces markdown internally (and may emit `REVIEW` via its
own rating regex). nomy-trader ignores that signal. After `graph.propagate`,
the runner asks the same configured model for a single JSON object. nomy-trader
validates with `extra=forbid` and required positive `entry` / `stop` / `target`.

`rating: REVIEW` is parseable then rejected so the error is explicit.

Alternatives rejected: regex on markdown; coercing `"N/A"` to null (repair);
silent Hold default.

## 5. Data-model / API

`SymbolAnalysis` gains `stop` and `why`. `signal` is the accepted rating, or
`UNAVAILABLE` when rejected. Cached runner payloads without
`structured_decision` fail closed until TTL expiry or `--force-reanalyze`.

## 6. Safety

- Output remains supplementary, not execution or sizing.
- Fail closed: no buy-scan promotion from unvalidated prose.
- Untrusted model text is never treated as instructions.

## 7. Implementation steps

1. Contract + reject reasons.
2. Wire `analyze_symbol`.
3. Runner JSON completion.
4. Tests, README, config note.

## 8. Tests

- Valid JSON maps to signal and quotes.
- REVIEW, omitted target, markdown-only, trailing comma → error, not Hold.
- `analyze_symbols` still records subprocess errors separately.

## 9. Rollback

Revert this plan's files; old regex parser returns. Cached structured payloads
remain harmless.

## 10. Open decisions

None for this milestone. Hold still requires numeric quotes (user: empty quotes
fail closed).
