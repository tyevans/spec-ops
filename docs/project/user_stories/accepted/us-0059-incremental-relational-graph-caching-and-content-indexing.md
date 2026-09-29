---
id: '0059'
title: Incremental Relational Graph Caching and Content-Addressed Entity Indexing
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-CORE-01
governing_prd: PRD-0005
---

# US-0059 — Incremental Relational Graph Caching and Content-Addressed Entity Indexing

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** agentic systems architect,
  - **I want** the SpecOps core graph compiler to maintain an incremental, content-addressed graph cache based on SHA-256 file hashes,
  - **So that** multi-thousand-entity project repositories can recompile relational graphs in sub-50 milliseconds on single-file changes rather than performing full repository filesystem AST re-scans.

## Acceptance Criteria

```gherkin
Scenario: Cold-start compilation generates content-addressed cache artifact
Given a repository containing 250 specification documents in "docs/project/"
And no existing graph cache file in ".specops/cache/graph.json"
When the architect runs "spec-ops stats --cache"
Then the command parses all 250 documents from disk
And writes a content-addressed cache artifact to ".specops/cache/graph.json"
And the cache contains SHA-256 content hashes, serialized entity models, and traceability edges
And reports "Graph compiled in cold state: 250 entities indexed, cache written".
```
```gherkin
Scenario: Hot incremental compilation after editing a single task
Given an established graph cache in ".specops/cache/graph.json" indexing 250 entities
When the architect modifies a single task file "docs/project/backlog/refined/0042-new-api.md"
And runs "spec-ops stats --cache"
Then the core parser reads only "docs/project/backlog/refined/0042-new-api.md" from disk
And retrieves the remaining 249 entities directly from the content-addressed cache
And re-links only the mutated node's incoming and outgoing traceability edges
And execution completes in under 50 milliseconds
And reports "Incremental graph sync: 1 file invalidated, 249 cache hits".
```
```gherkin
Scenario: Self-healing cache recovery upon checksum mismatch or corruption
Given an existing graph cache in ".specops/cache/graph.json" that has been truncated or corrupted
When the architect runs "spec-ops stats --cache"
Then the core graph compiler detects the corrupt cache payload
And logs a warning "Graph cache invalid: rebuilding index from source markdown"
And executes a clean full rebuild from disk
And rewrites a healthy ".specops/cache/graph.json" with exit code 0.
-
```

## Rationale & Compelling Value
- **Adoption**: Eliminates latency barriers when adopting PMaC in enterprise monorepos with thousands of tasks, ensuring instant tool execution.
  - **Regular Usage**: Powers snappy local pre-commit hooks, terminal commands (`health`, `stats`, `curate`), and visualizer updates during live typing.
  - **Compelling Value**: Unlike cloud SaaS tools with API rate limits, network roundtrips, and eventual consistency delays, SpecOps provides local-first, mathematically pure graph compilation running at native SSD speed.

---
