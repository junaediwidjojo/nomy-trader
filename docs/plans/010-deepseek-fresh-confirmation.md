# Fresh analysis with DeepSeek confirmation

Approved by the user's request to apply the proposed model selection and rerun
with fresh data on 15 October 2026.

Goal: rerun CRDO and CIEN without reusing saved analysis or market-data files.
Keep GPT-OSS 120B for the baseline and quick analyst/tool roles. Use DeepSeek
V4.1 Flash for confirmation's research and portfolio managers. Preserve strict
structured output and two debate rounds. No trading, messaging, sizing, or
watchlist implementation is included.

Relevant modules: analysis/profiles.py, analysis/pipeline.py, the single-symbol
runner, FMP prescreen, and CLI. No database schema changes are needed. Extend
the existing force flag rather than add another overlapping option. A fresh
temporary TradingAgents cache avoids deleting prior evidence. Stop before the
first bull researcher if either selected analyst report is empty; this gate
does not establish the factual correctness of nonempty reports.

Steps: update routing; propagate force through FMP and provider caches; add the
empty-report gate; run checks; fetch Ajaib and rerun the named stocks; inspect
the resulting evidence and model decisions. Confirmation still only runs
automatically for eligible baseline candidates; any additional audit must be
identified separately. Never force a bullish result or invent missing levels.

Validation: test missing-report rejection, unchanged quick routing, strict
portfolio binding, and forced FMP requests. Run formatting, lint, tests, and
type checks; distinguish pre-existing failures. Compare fresh run metadata,
report lengths, and decisions. Live provider requests can return the latest
available completed market session rather than today's intraday prices.

Rollback: revert routing and force propagation; preserve saved reports. Old
profile results have a different cache key. No unresolved design approvals.

Live finding: both first DeepSeek runs populated reports and returned valid
Portfolio Manager decisions, but Research Manager returned no structured
result. Extend native schema binding and the isolated 8192-token budget to
Research Manager too. A missing structured research review invalidates the
higher-profile decision even when a free-text fallback completes. Rerun both
review passes with fresh data; do not claim the first passes fully verified.

Completed: 206 tests pass; lint, changed-file formatting, and diff checks pass.
Full mypy retains the same 13 pre-existing errors; global formatting flags two
unchanged files. Fresh Ajaib fetch returned 1068 entries; FMP made two live
checks with zero reuse, and primary analysis had zero cache hits. Both repaired
two-round DeepSeek runs captured Research Manager, Trader, and Portfolio Manager
objects with zero structured errors and populated market/fundamentals reports.
All three roles returned Hold for each stock. Trader entry and stop were null,
so owned trade-plan validation correctly returned UNAVAILABLE. No confirmed
new buy, target, or cut-loss plan is approved by this run. Evidence is saved in
gitignored var/fresh_deepseek_verified_20261015.json and its Markdown summary.

22 October fresh-run finding: Yahoo returned the latest daily row with a null
Close while its regular-market quote had a timestamp at that session's close.
This made the existing loader discard October 21 and use October 20 despite
cache bypass. The initial batch was stopped; its results are diagnostic only.
The forced-data runner now fetches recent daily history, restores a missing
close only from Yahoo's matching-date regular-market quote timestamped at or
after 16:00 New York and within that day's low/high, and appends missing recent
sessions before computing indicators. Existing adjusted historical rows remain
intact. An unpriced completed bar blocks the refresh. Recovery is deliberately
conservative on early-close sessions. Per-tool requested dates, actual row dates,
quote timestamps, and values are saved in recent_ohlcv_refresh. A live SE check
now uses October 21, $77.94, matching the issuer's investor-page quote.

Final current-date audit also caught ARM and NTES tools selecting October 20.
Forced runs now pin tool curr_date/end_date to the runner's analysis date,
record requested/effective overrides, and preserve symbol/window parameters.
Targeted ARM baseline and NTES higher reruns both used October 21 prices.
211 tests pass; lint and changed-file formatting pass; the 13 existing mypy
errors remain. Two completed scans attempted 25 stocks, with zero cache reuse
and 45 live FMP checks. NTES was the sole baseline Overweight; its corrected
two-round DeepSeek review returned Hold, with no structured capture errors.
No approved buy plans resulted. The earlier stopped batch is diagnostic only.

Unresolved evidence-quality issue: NTES's analyst report mislabeled RMB amounts
as USD and misstated quarterly profit growth. The issuer's Q2 announcement
reports RMB30.1B (US$4.4B) revenue and RMB7.0B profit versus RMB8.6B a year
earlier. This run explicitly vetoes the preliminary NTES plan; automated
financial-currency and issuer-fact validation is not implemented. Do not treat
successful JSON parsing or two model passes as independent factual verification.
The full combined audit is in var/runs/20261022_summary.json and its Markdown
summary, including source URLs and rejected preliminary levels.

22 October follow-up, explicitly authorized by the user's request to fix the
unavailable higher signal and rerun NTES: distinguish a valid non-bullish
decision with null advisory prices from a failed model call. Keep explicit
entry/stop keys and paired-null validation; bullish ratings still require both
positive prices. Keep absent targets absent. Annotate financial tool evidence
with provider-reported financial and quote currencies before analyst use;
never convert financials or infer ADS/share units. Missing currencies block the
financial tool. Version profile cache identity to exclude old unlabeled evidence.
Test non-bullish null levels, bullish rejection and currency tool wiring; run
format/lint/type/tests, then fresh baseline and two-round higher NTES reviews
with isolated memory paths. Review the resulting reports against issuer facts.
This is a bug fix within the existing approved analysis workflow; no new order,
notification, or position behavior. Roll back these adapters if providers change;
preserve raw runs. Automated issuer-fact verification remains outside this fix.

Follow-up completed: 223 tests pass, including valid Hold/null prices, bullish
missing-price rejection, invalid supplied prices and currency-tool wiring.
Lint, changed-file formatting and diff checks pass; mypy retains the same 13
pre-existing errors. Fresh NTES baseline and higher runs both return Hold with
no validation or capture errors. Higher Research Manager, Trader and Portfolio
Manager all returned Hold; both debate limits were two rounds. Both runs used
October 21's USD122.98 close with CNY statement / USD quote metadata, empty
provider caches and isolated memory. No entry, stop or target was provided.
The earlier claim that null-price Hold correctly becomes UNAVAILABLE is
superseded: absence of a trade plan must not erase a valid non-bullish rating.

Currency labels are corrected in the live reports, but narrative inaccuracies
remain (including a wrong gaming-growth claim and a sequential comparison
described as YoY). No buy plan is approved; two structured passes are not
independent issuer-fact verification. Saved current results, provenance and
limitations are in var/runs/20261022_ntes_signal_fix/summary.md. The previous
latest candidate summary is preserved there; the latest targeted NTES summary
now contains zero bullish candidates. No commit or push was performed.
