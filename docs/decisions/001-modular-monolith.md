# ADR 001: Start with a modular monolith

## Status

Accepted.

## Decision

Use one Python repository, one primary process, and SQLite. Preserve interfaces
between domains without deploying them as separate services.

## Rationale

The project is hobby-scale. A monolith minimizes cost and operational burden
while still teaching boundaries, testing, scheduling, and integrations.

## Reconsider when

Measured workload, isolation, or reliability requirements cannot be met by one
process and database.

