---
id: '0057'
title: 'Architectural Spike: Content-Addressed SHA-256 Relational Graph Caching and
  Resilient AST Parsing'
status: Complete
dependencies:
- TASK-0004
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0059
- US-0061
target_bc: core
allows_dependencies: true
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0057: Architectural Spike: Content-Addressed SHA-256 Relational Graph Caching and Resilient AST Parsing

## Summary
Conduct a focused architectural spike to prototype and benchmark content-addressed SHA-256 relational graph caching and resilient Markdown AST parsing with precise frontmatter diagnostic source mapping. Validate sub-50 millisecond warm-cache compilation times for large PMaC repositories (~1,000 entities), test downstream dependency invalidation semantics upon single-file edits, verify transparent recovery from corrupted cache payloads, and establish resilient parser error boundaries that report precise line and column diagnostics without throwing unhandled exceptions.

## Problem Statement & Context
As PMaC repositories grow to hundreds of user stories, tasks, PRDs, and ADRs, full filesystem re-scanning and naive markdown re-parsing on every CLI command degrades interactive CLI latency and CI preflight performance. Furthermore, malformed YAML frontmatter (such as unquoted colons, invalid indentation, or missing delimiters) can cause unhandled parser crashes or catastrophic context drops during autonomous agent execution. SpecOps requires a verified content-addressed caching architecture and resilient AST error handling to achieve sub-50ms graph compilation and deterministic developer diagnostics.

## User Stories & Scenarios Satisfied
- **US-0059: Incremental Relational Graph Caching and Content-Addressed Indexing**
  - *Scenario: Compiling a 1,000-entity repository graph under 50 milliseconds using warm cache*
  - *Scenario: Invalidating only modified files and their downstream dependents on file change*
  - *Scenario: Recovering transparently from a corrupted cache file*
- **US-0061: Resilient Markdown AST Parsing and Precision Frontmatter Diagnostic Reporting**
  - *Scenario: Parsing valid markdown file preserving custom comments, tables, and fenced blocks*
  - *Scenario: Reporting precision line and column diagnostics on malformed YAML frontmatter*
  - *Scenario: Graceful handling of missing frontmatter delimiters with helpful scaffolding hint*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Spike prototype and benchmark harnesses in `src/spec_ops/core/spikes/cache_spike.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly generated file trees and arbitrary markdown contents verify that the cache lookup result is identical to cold graph compilation (cache transparency invariant) and that malformed inputs always yield structured diagnostics rather than unhandled exceptions.
- **Mutmut Mutation Scope**: Core hashing, cache serialization, and AST diagnostic recovery logic in `src/spec_ops/core/spikes/cache_spike.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Spike benchmarks compile time for a synthetic 1,000-entity graph, demonstrating cold compile in <1.2s and warm incremental compilation in <45ms.
2. Prototype accurately detects single-file SHA-256 hash changes and invalidates strictly that node and its immediate downstream dependents in the cached dependency tree.
3. Intentionally corrupted or truncated cache files are detected via checksums, logged at debug level, and discarded in favor of a cold rebuild without user-facing failures.
4. Markdown AST parser extracts frontmatter and body AST preserving tables and fenced code blocks, and returns structured diagnostic errors containing line, column, and snippet hints on malformed YAML.
5. All findings, benchmarks, and cache schema recommendations are published into `docs/project/adrs/proposed/adr-0015-content-addressed-graph-caching.md`.
