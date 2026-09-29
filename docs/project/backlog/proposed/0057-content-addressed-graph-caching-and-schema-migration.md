---
id: '0057'
title: Content-Addressed Incremental Graph Caching Engine, Precision AST Parsing, and Frontmatter Schema Migration
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0056
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
  - US-0017
target_bc: core
---

# TASK-0057: Content-Addressed Incremental Graph Caching Engine, Precision AST Parsing, and Frontmatter Schema Migration

## Summary
Implement production-grade content-addressed incremental graph compilation (`spec-ops graph compile [--incremental] [--json]`), resilient markdown AST parsing with precise diagnostic reporting, and automated in-place specification frontmatter schema validation and migration (`spec-ops schema validate`, `spec-ops schema migrate [--dry-run]`). Persist indexed entity nodes and dependency edges in `.specops/cache/graph.json` backed by file SHA-256 tree hashing, guarantee sub-50ms incremental graph resolution, and provide safe in-place YAML frontmatter normalization while preserving comments, markdown bodies, tables, and fenced blocks.

## Problem Statement & Context
Developers and autonomous agent workers frequently execute CLI inspection commands (`spec-ops stats`, `spec-ops health`, `spec-ops queue next`). Without incremental graph compilation, repeated parsing of entire specification trees causes sluggish terminal response and stalls CI pipelines. Additionally, specification schemas evolve over time (e.g. adding required metadata fields or renaming status values); manual schema updates across dozens of files invite errors and drift. SpecOps requires an incremental compilation engine coupled with automated schema migration tools to maintain specification hygiene.

## User Stories & Scenarios Satisfied
- **US-0059: Incremental Relational Graph Caching and Content-Addressed Indexing**
  - *Scenario: Compiling a 1,000-entity repository graph under 50 milliseconds using warm cache*
  - *Scenario: Invalidating only modified files and their downstream dependents on file change*
  - *Scenario: Recovering transparently from a corrupted cache file*
- **US-0061: Resilient Markdown AST Parsing and Precision Frontmatter Diagnostic Reporting**
  - *Scenario: Parsing valid markdown file preserving custom comments, tables, and fenced blocks*
  - *Scenario: Reporting precision line and column diagnostics on malformed YAML frontmatter*
  - *Scenario: Graceful handling of missing frontmatter delimiters with helpful scaffolding hint*
- **US-0017: Specification Frontmatter Schema Validation and Automated In-Place Migration**
  - *Scenario: Validating specification frontmatter against current schema*
  - *Scenario: Performing dry-run migration to inspect schema updates*
  - *Scenario: Executing in-place frontmatter migration preserving Markdown body contents*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Graph caching in `src/spec_ops/core/cache.py`, AST parsing in `src/spec_ops/core/ast_parser.py`, and schema migration in `src/spec_ops/core/migration.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that for any valid Markdown specification, `migrate(parse(spec))` preserves 100% of non-frontmatter body tokens verbatim (idempotent body preservation invariant).
- **Mutmut Mutation Scope**: Cache invalidation logic in `src/spec_ops/core/cache.py` and AST diagnostic parsing in `src/spec_ops/core/ast_parser.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops graph compile --incremental` compiles a warm 1,000-entity repository in under 50 milliseconds and writes cache to `.specops/cache/graph.json`.
2. Modifying a single markdown file causes subsequent `spec-ops graph compile --incremental` to re-parse strictly that modified file and invalidate dependent graph edges.
3. Executing `spec-ops schema validate` audits all files in `docs/project/` against active Pydantic schemas, exiting with code 0 if compliant or code 1 with line/column diagnostic pointers if invalid.
4. Executing `spec-ops schema migrate --dry-run` displays a unified diff of proposed frontmatter schema upgrades without touching disk.
5. Executing `spec-ops schema migrate --in-place` updates outdated frontmatter fields atomically while preserving Markdown body content, headings, tables, and fenced blocks verbatim.
6. All acceptance criteria verified through public CLI frontdoors via `pytest-bdd` without mock backdoors (ADR-0003, ADR-0006).
