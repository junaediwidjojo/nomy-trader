# Correct analysis inputs and structured outputs

Approved by the user's 27 October 2026 request to fix the observed issues,
then commit and push. This plan also includes the authorized, uncommitted
freshness and structured-output fixes documented in plan 010. Plan 009 remains
an unimplemented proposal and is excluded from this commit.

## Goal and scope

Prevent wrong-symbol provider calls, require a portfolio horizon at generation,
and replace error-prone financial-table narration with deterministic financial
evidence. Keep incomplete buy plans rejected. No trading, notifications, new
providers, dependencies, or watchlist implementation.

## Existing modules and design

The owned single-symbol runner adapts the sibling TradingAgents checkout.
Keep that checkout unchanged. Bind ticker/symbol arguments to the requested
instrument before provider calls and record requested/effective values. Keep
the existing forced-date audit. Enforce native JSON for the baseline managers
as well as higher managers, require a nonempty horizon, and explicitly explain
paired price fields to the Trader. Never fill omitted prices or horizons.

Replace the fundamentals analyst's free-form table generation with an owned
node that calls the same configured fundamentals/statement tools. Parse dated
provider CSV, retain units and frequency, and calculate margins/YoY with Decimal
and matching dates. Exclude EPS/share rows when ADS units are not established.
Record source snapshots and a content hash. Missing/invalid financial data
blocks debate. Other analyst/debate text remains unverified model commentary;
do not present deterministic tables as independent issuer-fact verification.

## Data model and failure behavior

Add raw-run provenance for symbol overrides and deterministic financial
evidence. Bump the profile contract version to avoid old reports. No database
migration. Preserve rejection of unsupported data, missing horizon, invalid
prices, missing native captures and incomplete bullish plans. A non-bullish
rating may retain partial advisory prices, explicitly flagged as an incomplete
plan; it must never become a buy candidate solely from those prices.

## Steps and verification

1. Add scoped tool arguments and regression tests for positional/keyword calls.
2. Strengthen manager schema binding and test null/missing/blank horizons.
3. Add deterministic financial evidence parser/renderer and node integration.
4. Test date ordering, frequency, currencies, missing values, incorrect CSV,
   arithmetic, unavailable year-ago periods and upstream wiring.
5. Run formatting, lint, type checks and tests. Distinguish baseline failures.
6. Run fresh targeted smoke analyses of the affected names; preserve failures
   as evidence and verify actual symbol/date, native output and financial facts.
7. Inspect the staged diff for secrets/private artifacts, commit and push the
   current fix branch. No PR was requested.

## Recovery and open decisions

Revert the owned adapters if the external schema changes; historical raw runs
are preserved. Provider freshness still differs from issuer publication
freshness; automated issuer reconciliation and unrestricted narrative fact
checking are not solved here. No risk-policy TBD is guessed. No further user
approval is required for this explicitly authorized fix and push.

## Completed validation

246 tests pass. Lint, changed-file formatting and diff checks pass. Full mypy
retains the same 13 existing errors in the Ajaib client, CLI and pipeline
protocol; the new financial-evidence module adds no errors. Regressions cover
wrong-symbol calls before both provider data and currency lookup, required
nonempty horizons, native Trader binding, complete bullish plan requirements,
invalid long geometry, date ordering, exact year-ago comparisons, currencies,
invalid/annual/future data, omitted ADS units and financial-node wiring.

Five fresh live profiles completed with zero structured capture errors:
NTES baseline Hold, NTES higher two-round Hold, PAGS Underweight, MRNA
Underweight and MOD Hold. All required managers/Trader objects and horizons
were present. Each saved financial ledger was regenerated from its captured
source CSV and matched exactly, including its hash. NTES's financial report
now reports revenue growth of 7.9410% and net-income decline of 18.8391% from
matching quarterly periods, retaining CNY financial / USD quote units.
The later EPS/profile filtering is covered by node tests; the early live
baselines preceded that narrow filtering adjustment. Results and verification
are preserved in ignored var/runs/20261027_fixes/. No bullish result is forced.

Decision clients receive the canonical ledger directly rather than relying
only on debate summaries. Qualitative model commentary, forecast dates,
provider freshness relative to issuer releases and issuer agreement remain
unverified; do not claim this fixes every possible model hallucination.
