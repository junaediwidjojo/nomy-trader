# Roadmap — recommendation MVP

Scope changed 2026-09-08. Active plan: [scope revision](plans/001-mvp-scope-revision.md).
Implement one approved milestone at a time; checklist S01–S29 is the resume record.
Original numbered roadmap is preserved in [archive](archive/ibkr-design/ROADMAP.md).

1. **Changed — recommendation contracts:** reuse valid domain work; remove broker
   coupling and add advisory sizing/policy inputs and notification scenarios.
2. **Changed — SQLite journal foundation:** move persistence earlier so quota,
   cache, recommendations and delivery intents survive restarts.
3. **Changed — FMP scanner:** verify free-tier entitlements, implement quota-aware
   losers/screener discovery, then recompute eligibility from quotes/history.
4. **Retained — evidence and AI:** immutable sources and strict buy-side analysis.
5. **Changed — complete plans and advisory risk:** deterministic valuation/size;
   explicitly approved treatment of unavailable portfolio inputs.
6. **Changed — Telegram terminal delivery:** durable recommendation and outbox,
   outbound notifications only; no confirmation or execution.
7. **Changed — informal evaluation and operation:** CLI exports, daily report,
   budget-aware scheduling and recovery. No automated performance/fill tracking.

## Deferred and dropped from MVP

- Original milestones 8 (IBKR read-only) and 9 (IBKR paper execution): deferred
  entirely; no broker data, reconciliation, holdings or orders in MVP.
- Original milestone 10 position management: dropped from MVP. Scheduling now
  governs discovery and notifications only. Future execution requires a new plan.
- Original milestone 7 formal AI-versus-baseline evaluation: deferred; current
  forward recommendation journal supports manual comparison.
- Confirm/reject Telegram interactions: fast-follow, not MVP.
- Live system execution remains outside all approved work. IBKR automation is a
  preserved possible future direction, not an MVP prerequisite.
