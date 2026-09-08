# Evaluation — informal MVP benchmarking

Changed 2026-09-08. Formal AI-versus-baseline evaluation is deferred; the
[original methodology](archive/ibkr-design/EVALUATION.md) remains future work.

Log every recommendation before notification: full TradePlan, schema/policy and
model/prompt versions, evidence, quote/creation timestamps, suggested size and
its assumptions. Record Telegram-confirmed send time/status separately. Keep
failed/unknown deliveries distinguishable in exports and never count them as
confirmed sent. Preserve revisions and rejected analysis records for audit.

Provide JSON/CSV exports for the user to compare manually with actions in their
separate app and later stock prices. MVP does not import fills, infer execution
from a message, track positions, or compute realized P&L. No automated outcome
fetching is required; any future price collection needs its own quota allocation.
Manual observations are not backtested returns or proof that AI adds value.

Verify temporary damage, permanent repricing, governance, sector decline,
no-news, conflicting/late/revised evidence, stale quotes, invalid model output,
quota exhaustion, database failure and notification retries/ambiguity. Broker
partial fills/reconciliation tests are deferred with broker scope. Tests must
prove full-plan persistence before send and no new recommendation on missing
mandatory policy/data. Keep point-in-time provenance even for informal review.

Report uncertainty and data limitations. Any future quantitative performance
study must separately address selection bias, missed recommendations, costs,
slippage, drawdowns and faithful historical inputs. None are assumed resolved
by this recommendation log.
