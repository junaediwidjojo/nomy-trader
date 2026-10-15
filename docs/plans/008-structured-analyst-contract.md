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

## Defect repair — 15 October 2026

CRDO and CIEN higher-model confirmations omitted required `investment_thesis`
in PortfolioDecision tool arguments. The compatible client uses automatic
tool selection and function calling without schema-enforced generation; typed
validation then failed and the runner fell back to markdown. This was an
output-format failure, not a successfully validated confirmation rating.

Keep this repair within the approved runner/intercept scope: higher-model
profiles now select native `json_schema` with strict binding and explicit
schema instructions for Portfolio Manager only. Research Manager and Trader
retain their original bindings. Rebind agent-local `bind_structured` before graph
construction (capture still installs afterward). Do not change TradingAgents
schemas, fill missing thesis/price fields, add an extraction LLM, or accept
markdown. The profile override participates in the existing cache hash, so
old confirmation failures do not mask the fix. Baseline dispatch stays intact.

Fireworks documents that native schema mode suppresses separate reasoning
output for structured calls. Analyst/debate calls are unchanged; the final
decision still receives the debate evidence and must supply a thesis.
Validate with mocked provider payloads, regression tests, and bounded live
decision calls before claiming a successful repair. A valid Hold with null
Trader levels must still remain UNAVAILABLE under the owned contract.

The saved CRDO debate replay also reproduced `LengthFinishReasonError`:
2,400 completion tokens included 2,000 reasoning tokens, leaving only 400
for the structured answer. Native schema enforcement alone cannot overcome
truncation. Higher-model profiles therefore give Portfolio Manager an explicit
8,192-token budget on a cloned client; other agents retain their existing
budgets. Both overrides enter the cache identity. The larger maximum can
increase cost, but only for that final decision call.

Verification: 202 offline tests passed; repository lint and changed-code format
checks passed. HTTP transport inspection verified native strict schema and
8,192 tokens on the Portfolio Manager clone, with the original client still
at 2,400. Live replays of the saved CRDO and CIEN debates through the actual
Portfolio Manager node both produced complete typed Hold decisions with a
thesis and no capture errors. Proof is in gitignored
`var/portfolio_schema_replay_fixed_20261015.json`. These are saved-evidence
replays, not new full research confirmations. The earlier experiment applying
native schema to all decision agents timed out after 900 seconds; the final
repair narrows the change to Portfolio Manager and was not followed by another
full debate run. Type checking still reports the same 13 errors reproduced
against unmodified HEAD in a temporary checkout.
