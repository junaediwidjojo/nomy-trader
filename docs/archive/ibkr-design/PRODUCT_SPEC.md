# Product specification

## Problem

Large stock-price declines sometimes reflect new fundamental information and
sometimes may exceed the event's plausible economic damage. The project tests
whether bounded AI analysis of current evidence adds value over a deterministic
quantitative baseline in distinguishing these cases.

## Product statement

An event-driven, AI-assisted paper-trading system that scans liquid stocks for
abnormal declines, investigates the triggering event using typed evidence
tools, creates an auditable trade thesis and complete exit plan, applies hard
risk controls, and manages the paper position until closure.

## Users

- Primary: one technically capable hobbyist learning AI engineering.
- Secondary: portfolio reviewers evaluating engineering decisions.

## Goals

- Learn tool calling, structured outputs, evaluation, stateful workflows,
  external APIs, observability, and safe consequential actions.
- Test the event-driven overreaction hypothesis without risking capital.
- Produce reproducible evidence about whether AI improves the baseline.
- Maintain an auditable lifecycle for every candidate and position.

## Non-goals

- Guaranteed or advertised profitability.
- High-frequency or low-latency trading.
- Whole-market tick processing.
- Options, leverage, short selling, crypto, or foreign exchange initially.
- RAG or a vector database initially.
- Microservices, Kubernetes, Kafka, or a web dashboard initially.
- Live trading before explicit promotion criteria are met.

## Buy workflow

1. Request an IBKR market scan for percentage decliners when supported, or
   calculate decliners from the configured liquid universe.
2. Retrieve quotes and bars separately and apply deterministic quality,
   liquidity, volatility, duplicate-event, and data-freshness filters.
3. Identify the event associated with the decline.
4. Retrieve time-bounded news and primary sources available at decision time.
5. Compare the company with sector, peers, and broader market.
6. Have bounded AI classify the event and state uncertainty.
7. Calculate scenario valuation deterministically from explicit assumptions.
8. Require a complete TradePlan: entry ceiling, valuation range, targets, stop,
   expected duration, maximum duration, thesis, invalidations, and evidence.
9. Apply deterministic portfolio risk policy.
10. Submit an idempotent paper order.
11. Only after broker fill confirmation, open the position and attach its plan.

## Sell workflow

1. Reconcile actual broker positions, open orders, cash, and fills with SQLite.
2. Continuously evaluate deterministic price, risk, protection, and time exits.
3. Trigger AI thesis review only on new material evidence, abnormal movement,
   scheduled daily review, or approaching expiry.
4. Permit structured recommendations: HOLD, REDUCE, EXIT, or RAISE_STOP.
5. Never permit AI to lower a stop merely to avoid recognizing a loss.
6. Apply the risk engine, submit an idempotent paper order, and record fills.
7. Close the plan with realized outcome, costs, slippage estimate, and review.

## Core invariants

- Top loser is a candidate, never a buy signal.
- No entry without a complete exit plan.
- No open broker position without one active internal plan.
- Broker state is authoritative for cash, positions, orders, and fills.
- SQLite is authoritative for thesis, evidence, valuation, and exit policy.
- Reconciliation failure freezes new entries.
- Model or evidence-provider failure cannot disable hard exits.

## Success

Learning success means the owner can explain and defend the architecture,
evaluation, safety boundaries, and implementation. Strategy success requires
out-of-sample and paper evidence after costs; it is not presumed.

