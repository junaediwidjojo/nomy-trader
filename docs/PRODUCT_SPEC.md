# Product specification — nomy-trader recommendation MVP

Changed 2026-09-08. [Original automation design](archive/ibkr-design/PRODUCT_SPEC.md)
is retained as future direction; no broker integration belongs in this MVP.

For one hobbyist, investigate potentially excessive stock declines and send
complete, auditable buy-side ideas. Educational success and useful evidence are
the goals; profitability is not assumed. The user manually chooses price and
size and executes elsewhere. The application never learns whether they bought.

## Workflow

1. Discover candidates with FMP's biggest-losers endpoint, then require a match
   in the local Ajaib U.S.-stock catalogue before further work. Ajaib one-day
   change is retained as snapshot context only, never the daily trigger.
2. Recompute deterministic liquidity, decline, volatility and freshness filters
   from FMP quote/volume/history data within the verified free-tier budget.
3. Collect time-bounded news, disclosures and company/market context.
4. Have a bounded model classify evidence and uncertainty; reject invalid output.
5. Calculate valuation and suggested size using deterministic approved policy.
6. Require every applicable complete TradePlan field, including advisory exits.
7. Atomically log the full recommendation and notification intent to SQLite.
8. Send Telegram symbol, entry ceiling/suggested price, suggested quantity or
   USD value, stop, targets, thesis summary and confidence/uncertainty, with plan
   identity/time and sizing basis. No confirm/reject buttons or reply processing.
9. Export the journal for informal manual comparison with later prices/actions.

## Boundaries and acceptance

No broker API, orders, reconciliation, positions, automated sell/exit logic or
fill capture. Stop/target fields are not installed protection. Delivery cannot
imply a purchase; the system cannot enforce user execution size or price.
Risk checks concern the recommendation and explicitly available inputs only;
unavailable portfolio limits require a recorded decision before release.

## Ajaib availability boundary

The user manually trades through Ajaib. Ajaib's U.S. catalogue is a selected,
changing subset of U.S. listings, so a U.S. ticker alone is insufficient. A
candidate must match a versioned, immutable local Ajaib catalogue before it can
pass discovery. A missing or ambiguous match rejects the candidate; the
application must not imply that an instrument is tradeable in the user's account.
The catalogue is manually refreshed from a user-supplied crawl; its revision and
retrieval timestamp remain visible rather than silently claiming live availability.
This is an availability gate only, not a broker integration, account query or
order capability.

MVP acceptance: budget-safe discovery; complete validated logged plans; reliable,
recoverable outbound delivery with honest failure status; useful full-plan
exports; and tested failure behavior. Local CLI/reports precede supervised Linux
operation. No dashboard, formal backtest or claim of AI superiority is required.
