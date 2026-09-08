# Execution plans

For any significant feature or refactor, write a self-contained ExecPlan in
`docs/plans/` before implementation. A new contributor must be able to execute
it using only the repository and the plan.

Each ExecPlan must contain:

1. Goal and user-visible outcome.
2. Scope and explicit non-goals.
3. Relevant existing modules and specifications.
4. Proposed design and alternatives considered.
5. Data-model or API changes.
6. Safety invariants and failure behavior.
7. Ordered implementation steps.
8. Test and validation plan.
9. Rollback or recovery approach.
10. Open decisions requiring user approval.

Keep the plan updated as implementation discovers new facts. Record deviations
and their reasons. Do not resolve domain `TBD` values by guessing.

