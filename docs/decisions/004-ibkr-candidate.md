# ADR 004: IBKR is the candidate broker

> Historical future-direction material as of 2026-09-08. IBKR data and
> execution are out of MVP scope; see [ADR 005](005-recommendation-only-mvp.md).
> Original text below is retained, not a current integration requirement.

## Status

Provisional, pending account approval and entity verification.

## Decision

Design a provider-neutral broker interface and target the official IBKR TWS API
for read-only integration and later paper execution.

## Rationale

IBKR offers global market access, API market scanners, account/position data,
market data, and paper trading. It appears suitable for an Indonesian hobbyist,
subject to individual onboarding and product permissions.

## Required verification before funding

- Account application is accepted for the user's Indonesian residency.
- Record the exact contracted IBKR legal entity.
- Read that entity's customer agreement, regulator, custody arrangement, and
  investor-compensation/protection scheme.
- Confirm U.S. stock permissions, fees, FX/funding costs, tax documentation,
  market-data subscriptions, and paper API access.
- Enable strong authentication and test withdrawals manually.

Broker legitimacy and custody protections do not protect against investment
loss, automation defects, currency risk, tax obligations, outages, or every
form of fraud/cyber loss.

