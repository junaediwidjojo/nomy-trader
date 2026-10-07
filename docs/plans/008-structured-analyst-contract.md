# Structured analyst decision contract

Status: approved for implementation 2026-09-15 by user request (AI-engineering
milestone 1: own the contract).

## 1. Goal and user-visible outcome

nomy-trader accepts a TradingAgents review only when the runner supplies a JSON
object matching `{rating, entry, stop, target, horizon, why}`. Entry and stop
are required. Target may be null. `REVIEW`, missing entry/stop, or prose-only
markdown fail closed. The pipeline does not regex-repair `**Rating**`.

Deviation 2026-09-15: keep Buy/Overweight when entry and stop exist even if
TradingAgents omitted a price target. REVIEW is only for missing entry/stop.

Deviation 2026-09-15 (LLM use): intercept TradingAgents structured objects by
rebinding `invoke_structured_or_freetext` on each agent module after import.
No second extraction LLM. If Fireworks falls back to markdown, fail closed.

CLI rows show `UNAVAILABLE` plus a rejection reason instead of a guessed Hold.

## 2. Scope and non-goals

**In scope**

- Pydantic contract in nomy-trader.
- JSON-only accept path in `analyze_symbol`.
- Capture TradingAgents Portfolio Manager + Trader structured dumps in the
  runner and map them to the nomy-trader contract. No second LLM extraction.
- Tests for accept, REVIEW, missing entry/stop, markdown-only, malformed JSON.

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

TradingAgents still produces markdown internally for reports. The Portfolio
Manager and Trader already emit typed Pydantic objects; the runner captures
those before `render_*` turns them into markdown. nomy-trader maps PM
`rating` / `price_target` / `time_horizon` / `executive_summary` and Trader
`entry_price` / `stop_loss`. Markdown fallback or missing entry/stop fail closed.

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
- REVIEW, omitted stop, markdown-only, trailing comma → error, not Hold.
- Overweight with entry/stop and null target is accepted.
- `analyze_symbols` still records subprocess errors separately.

## 9. Rollback

Revert this plan's files; old regex parser returns. Cached structured payloads
remain harmless.

## 10. Open decisions

None for this milestone. Target is optional; entry and stop are not.
