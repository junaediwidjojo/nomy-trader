# Resume prompt — recommendation MVP

Read AGENTS.md, PLANS.md, docs/plans/001-mvp-scope-revision.md and the active
specifications. Treat archived IBKR documents and 001-domain-contracts.md as
historical. The scope is FMP discovery, complete buy-side recommendations,
SQLite logging and outbound Telegram. No broker integration or automated exits.

Before approval: review the ten-section ExecPlan and open decisions only; do not
implement. After explicit approval: start at the first unchecked approved step,
read its Resume note, implement and verify only that step, update its checkbox,
and commit its code plus plan together. Record incomplete work and exact next
actions under the checkbox if interrupted. Never infer a completed step from
partial source files. Git initialization itself is pending; see S01.

Previous partial code implements old offline broker contracts and is not an
approved revised MVP. Record decisions rather than guessing trading thresholds.
