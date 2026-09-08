# ADR 003: Do not use RAG initially

## Status

Accepted.

## Decision

Retrieve current prices, evidence, filings, financial facts, and portfolio state
on demand through typed tools. Do not add embeddings or a vector database.

## Rationale

The initial problem requires narrow, current, source-specific retrieval. RAG
adds ingestion and evaluation complexity without an established need.

## Reconsider when

Measured retrieval failures show that semantic access to a large historical
corpus of theses or documents would materially improve quality.

