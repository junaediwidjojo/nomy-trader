# Factual audit of the 27 October 2026 analysis

Reviewed manually on 27 October 2026 against issuer releases and SEC filings.
Scope: material financial and catalyst claims in the latest NTES baseline/higher
reports and PAGS, MRNA and MOD baseline reports after commit `320691c`.
Local immutable evidence: ignored `var/runs/20261027_fixes/*_raw.json`.
These findings supersede conflicting model commentary, without rewriting the
historical reports or silently changing provider observations.

**Result: factual review failed. No reviewed report is cleared as a complete,
fact-verified investment recommendation.** Deterministic provider arithmetic
passed earlier checks; issuer reconciliation exposes additional discrepancies
and missing context. A successful JSON response or two model passes is not a
successful factual audit. This document is a manual audit, not an automated gate.

## NetEase — NTES

| Claim | Finding |
|---|---|
| Revenue grew about 7.94%; shareholder profit fell 18.84% YoY | Supported by matching June-quarter figures: revenue RMB30.106546bn versus RMB27.891664bn; attributable profit RMB6.980656bn versus RMB8.601010bn. |
| Baseline's 27.9% margin describes the current quarter | Wrong period/basis. Attributable profit divided by revenue gives 23.1865%. Do not conflate it with a trailing ratio. |
| Higher report treats operating/net-profit divergence as unexplained | Missing context. The issuer discloses RMB2.953671bn investment loss, exchange losses, and a higher effective tax rate. Absence from selected provider rows is not absence from public evidence. |
| Approximately RMB10bn is the company's total net cash | Incomplete definition. Cash equivalents less provider debt is narrower than issuer net cash, RMB167.5bn including deposits and short-term investments less loans. |
| Next results are in early November | Not verified from an issuer announcement retrieved in this audit; do not use as a confirmed date. |

Source: [20 August issuer release and detailed financial tables](https://netease.gcs-web.com/news-releases/news-release-details/netease-announces-second-quarter-and-interim-2026-unaudited).

## Moderna — MRNA

| Claim | Finding |
|---|---|
| Revenue collapsed 79% to USD143m | Unspecified comparison, unsuitable as a current YoY claim. Issuer release has USD145m versus USD142m, about +2.11% YoY; provider has USD143m versus USD137m. Provider/issuer mismatch remains unresolved. |
| Quarterly net loss USD782m and operating loss USD815m | Supported by issuer financial tables. |
| Only 7–8 months of runway | Unsupported calculation. Issuer reports USD6.9bn cash/equivalents/investments and forecasts USD4.7–5.2bn at year-end; this does not establish a precise runway. |
| Next earnings are approximately 6–12 months away | Contradicted by issuer event listing: Q3 call on 6 November 2026. |
| Earliest candidates are at least two years away | Blanket statement conflicts with the issuer's near-term regulatory milestones. It cannot substitute for product-specific verification. |

Sources: [issuer-authored Q2 release distributed on Nasdaq](https://www.nasdaq.com/press-release/moderna-reports-second-quarter-2026-financial-results-and-provides-business-updates),
[issuer event listing](https://investors.modernatx.com/events-presentations).
The event page's dynamic open response omitted listings; its indexed issuer
listing supplied the date. Treat future schedules as subject to change.

## Modine — MOD

| Claim | Finding |
|---|---|
| Quarterly revenue +28%, attributable earnings about +44% | Supported: USD874.1m sales and USD73.9m attributable earnings; consolidated net earnings are USD74.3m, a different measure. |
| Provider operating income USD78.7m is GAAP operating income | Definition mismatch: filing reports USD74.8m after USD3.9m restructuring expense. Do not silently relabel standardized provider data. |
| Next earnings are approximately three months away | Wrong: results scheduled after market close 3 November, call 4 November 2026. |
| June-quarter consolidated valuation is sufficient for today's business | Material context missing: Performance Technologies spin-off/combination completed 1 October. Continuing-business valuation needs reconciliation. |

Sources: [Q1 FY2027 SEC filing](https://www.sec.gov/Archives/edgar/data/67347/000110465926088569/mod-20260630x10q.htm),
[earnings schedule](https://investors.modine.com/news/news-details/2026/Modine-to-Host-Second-Quarter-Fiscal-2027-Earnings-Conference-Call-on-November-4-2026/default.aspx),
[transaction completion](https://investors.modine.com/news/news-details/2026/Modine-Completes-Spin-off-and-Combination-of-its-Performance-Technologies-Business-with-Gentherm/default.aspx).

## PagBank — PAGS

| Claim | Finding |
|---|---|
| Quarterly total revenue BRL5.080bn and GAAP profit BRL549m | Supported. Ex-ITC revenue BRL3.380bn and non-GAAP profit BRL576m are different measures, not interchangeable corrections. |
| Debt/equity approximately 11.8 times | Not reproduced. Saved provider debt BRL44.287bn divided by equity BRL15.016bn is 2.9493 times. Filing separates banking issuances, checking accounts and borrowings; corporate-debt distress assumptions require a bank-specific reconciliation. |
| A price decline permits locking in gains on existing holdings | Unsupported: no user's entry price, holdings or cost basis was supplied. |
| Interest coverage below 0.25 times and inevitable dividend stress | Not established by the verified evidence; do not use these assertions to justify sizing, shorts or hedges. |

Source: [issuer Q2 2026 results filed on Form 6-K](https://www.sec.gov/Archives/edgar/data/1712807/000155485526001793/MainDocument.htm).

## Consequences and limits

Keep these names as research observations, not fact-cleared trade instructions.
Do not apply model position weights, trim percentages, shorts or options to
unknown holdings. No orders, alerts or revised buy recommendations were issued.
Technical indicators, valuation forecasts, clinical timelines and every minor
sentence were not independently revalidated here; unsupported means unverified,
not proof of the opposite. Future runs still need their own dated fact review.

Validation for this change: documentation-only diff and source-link review;
application code is unchanged from the previously tested 246-test commit.
