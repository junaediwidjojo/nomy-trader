# ADR 002: Paper trading is the execution boundary

> Historical future-direction material as of 2026-09-08. IBKR data and
> execution are out of MVP scope; see [ADR 005](005-recommendation-only-mvp.md).
> Original text below is retained, not a current integration requirement.

## Status

Accepted.

## Decision

Only IBKR paper execution is permitted in the initial project. Live trading is
not a configuration toggle shipped alongside paper mode.

## Rationale

Strategy edge and operational correctness are unproven. Keeping live execution
absent reduces the consequence of software, model, and process failures.

## Consequence

Any live proposal requires a new ADR, review, evaluation report, threat model,
runbook, minimal-capital rollout, and explicit approval.

