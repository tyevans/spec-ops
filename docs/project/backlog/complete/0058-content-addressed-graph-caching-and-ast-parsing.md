---
id: 0058
title: Content-Addressed Incremental Graph Caching Engine and Precision AST Parsing
status: Complete
dependencies:
- TASK-0057
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
- ADR-0009
- ADR-0015
governing_prds:
- PRD-0005
governing_stories:
- US-0059
- US-0061
target_bc: core
---

# TASK-0058: Content-Addressed Incremental Graph Caching Engine and Precision AST Parsing

## Summary
Graduate the empirical findings of architectural spike TASK-0057 into production-grade core capabilities: implement content-addressed incremental graph compilation (`spec-ops graph compile [--incremental] [--json]`) and resilient markdown AST parsing with precise diagnostic reporting (`spec-ops parse <file>`). Persist indexed entity nodes and dependency edges in `.specops/cache/graph.json` backed by file SHA-256 tree hashing, guarantee sub-50ms incremental graph resolution, and gracefully handle malformed markdown or YAML syntax with helpful error pointers and scaffolding suggestions.

## Problem Statement & Context
Developers and autonomous agent workers frequently execute CLI inspection commands (`spec-ops stats`, `spec-ops health`, `spec-ops queue next`). Without incremental graph compilation, repeated parsing of entire specification trees causes sluggish terminal response and stalls CI pipelines. Spike TASK-0057 demonstrated that SHA-256 tree hashing and incremental parsing achieve sub-50ms graph compilation while resilient AST parsing recovers gracefully from syntax anomalies. TASK-0058 integrates these verified spike patterns into SpecOps core architecture.

## User Stories & Scenarios Satisfied
- **US-0059: Incremental Relational Graph Caching and Content-Addressed Indexing**
  - *Scenario: Compiling a 1,000-entity repository graph under 50 milliseconds using warm cache*
    - Given a repository containing 1,000 markdown specifications and an initialized cache in ".specops/cache/graph.json"
    - When the developer executes "spec-ops graph compile --incremental"
    - Then the command compiles the complete graph in under 50 milliseconds
    - And outputs cache hit statistics indicating zero cache misses.
  - *Scenario: Invalidating only modified files and their downstream dependents on file change*
    - Given an existing valid graph cache
    - When a single task specification is modified on disk
    - And the developer executes "spec-ops graph compile --incremental"
    - Then only the modified file and its direct graph neighbors are re-parsed
    - And unchanged specifications are served from cache.
  - *Scenario: Recovering transparently from a corrupted cache file*
    - Given a corrupted or invalid JSON cache file in ".specops/cache/graph.json"
    - When the developer executes "spec-ops graph compile --incremental"
    - Then the system logs a warning indicating cache corruption
    - And transparently falls back to a cold compilation rebuild without failing.
- **US-0061: Resilient Markdown AST Parsing and Precision Frontmatter Diagnostic Reporting**
  - *Scenario: Parsing valid markdown file preserving custom comments, tables, and fenced blocks*
    - Given a specification document containing markdown tables, comments, and code blocks
    - When parsed through the resilient AST parser
    - Then all non-frontmatter structural tokens are preserved.
  - *Scenario: Reporting precision line and column diagnostics on malformed YAML frontmatter*
    - Given a specification file with invalid YAML indentation on line 4, column 3
    - When the developer executes "spec-ops parse <file>"
    - Then the command reports a diagnostic pointing precisely to line 4, column 3 with remediation hints.
  - *Scenario: Graceful handling of missing frontmatter delimiters with helpful scaffolding hint*
    - Given a plain text document without frontmatter delimiters
    - When the developer executes "spec-ops parse <file>"
    - Then the parser surfaces a structural warning and suggests a scaffold template.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Graph caching in `src/spec_ops/core/cache.py` and AST parsing in `src/spec_ops/core/ast_parser.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that arbitrary perturbations to non-dependent specification files never alter the compiled graph edges of unrelated subgraphs.
- **Mutmut Mutation Scope**: Cache invalidation logic in `src/spec_ops/core/cache.py` and AST diagnostic parsing in `src/spec_ops/core/ast_parser.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops graph compile --incremental` compiles a warm 1,000-entity repository in under 50 milliseconds and writes cache to `.specops/cache/graph.json`.
2. Modifying a single markdown file causes subsequent `spec-ops graph compile --incremental` to re-parse strictly that modified file and invalidate dependent graph edges.
3. Transparent recovery from corrupted cache files without process crash.
4. Executing `spec-ops parse <file>` reports precise line/column diagnostics for invalid frontmatter.
5. All scenarios executed via `pytest-bdd` against CLI frontdoors with zero mock backdoors (ADR-0003, ADR-0006).
