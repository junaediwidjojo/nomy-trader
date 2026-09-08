# Broker due diligence — Interactive Brokers

> Historical future-direction material as of 2026-09-08. IBKR data and
> execution are out of MVP scope; see [ADR 005](decisions/005-recommendation-only-mvp.md).
> Original text below is retained, not a current integration requirement.

## Status

Verified on 2026-09-08 only as a plausible, regulated broker candidate. This is
not a guarantee of safety, eligibility, execution quality, or investment return.

## Supporting facts

- Interactive Brokers LLC appears on SIPC's member list.
- SIPC states that eligible customers of a SIPC-member firm, including non-U.S.
  citizens, may receive protection up to USD 500,000 including a USD 250,000
  cash sublimit when assets are missing after broker failure. Coverage depends
  on the actual member entity and asset/account type.
- SIPC does not protect declines in investment value, bad advice, most
  commodities/FX, or many digital assets.
- IBKR describes segregation/reserve practices for client money and publishes
  information about its financial strength and business-continuity planning.
- IBKR paper accounts support its Web and TWS APIs with some simulation
  differences.

## Sources

- SIPC member list: https://www.sipc.org/list-of-members
- SIPC protection scope: https://www.sipc.org/for-investors/what-sipc-protects
- IBKR client protection: https://www.interactivebrokers.com/en/general/security-investor-protection.php
- IBKR financial strength: https://www.interactivebrokers.com/en/general/financial-strength.php
- IBKR API overview: https://www.interactivebrokers.com/en/trading/ib-api.php
- IBKR paper-account API: https://www.interactivebrokers.com/campus/glossary-terms/paper-trading-account/

## Mandatory onboarding checklist

Before depositing meaningful money:

1. Complete the application using the official IBKR domain/application only.
2. Record the exact legal entity shown in the customer agreement; do not assume
   it is Interactive Brokers LLC.
3. Independently verify that entity with its named regulator and applicable
   compensation/protection scheme.
4. Confirm Indonesian residency acceptance, U.S. stock permissions, tax forms,
   funding/withdrawal routes, FX costs, commissions, and data subscriptions.
5. Enable strong authentication and account alerts.
6. Start with the paper account; later test a small deposit and withdrawal.
7. Do not enable margin, options, stock lending, or other programs unless their
   separate risks are understood and intentionally accepted.

## Risks that remain

- Stock prices can fall and losses are not insured.
- Automated strategies can malfunction or behave differently in live markets.
- Orders can be delayed, rejected, partially filled, or filled with slippage.
- Market data and broker sessions can become stale or unavailable.
- Account takeover, phishing, device compromise, and credential leakage remain
  possible.
- Cross-border tax, currency, custody, and legal treatment can change.

Re-run this due diligence immediately before opening or funding the account.

