---
id: '0133'
title: Redstring Relational Knowledge Graph and AST Projection
status: Complete
dependencies:
- TASK-0058
- TASK-0128
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
- ADR-0009
- ADR-0011
- ADR-0015
- ADR-0017
governing_prds:
- PRD-0001
- PRD-0005
governing_stories:
- US-0016
- US-0059
target_bc: graph
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T11:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0133: Redstring Relational Knowledge Graph and AST Projection

## Summary
Implement the formal relational knowledge graph substrate governed by ADR-0011 using `redstring` entity-relationship models and deterministic `SpecOpsFrontmatterExtractor`. Transition graph query operations (`spec-ops graph reach`, `spec-ops graph blast-radius`, `spec-ops graph orphan-audit`) to native graph neighbor traversal while preserving sub-50ms compilation latency via SHA-256 content-addressed caching.

## Problem Statement & Context
SpecOps builds a living graph connecting Personas -> PRDs -> Stories -> Tasks -> ADRs -> Commits. Previous graph traversal relied on ad-hoc regular expressions (`re.findall(r"PRD-\d+", ...)`) and nested list scans that degraded on large repositories and struggled with entity alias resolution. ADR-0011 establishes a formal knowledge graphing substrate with native graph value types (`Entity`, `Relationship`) and fast topological querying.

## Key Requirements & Scope
1. **Deterministic SpecOps Frontmatter Extractor (`src/spec_ops/graph/redstring_bridge.py`)**:
   - Zero-LLM requirement: extracts entities and typed relationships directly from parsed Markdown YAML frontmatter and markdown body AST.
   - Maps PRD checkable outcomes, task dependencies, persona pain points, and governing ADR references to typed graph relationships (`satisfies`, `depends_on`, `governed_by`, `authored_by`).
2. **In-Memory Graph Store & Content-Addressed Caching**:
   - Implements `InMemoryGraphStore` substrate compiling full repository graphs in <50ms.
   - Caches graph snapshots to `.specops/cache/graph.json` keyed by SHA-256 file contents hashes (ADR-0015).
3. **Graph Traversal & Reachability Frontdoors**:
   - Re-implements `spec-ops graph reach` and blast-radius analysis using native graph traversal.
   - Adds alias consolidation resolving persona nicknames and alternative task identifiers.
   - 100% blackbox frontdoor tests and Hypothesis property invariants.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: New redstring bridge module in `src/spec_ops/graph/redstring_bridge.py` must stay strictly under 400 lines (ADR-0002).
- **Sub-50ms Graph Compilation (ADR-0011, ADR-0015)**: Graph caching ensures compilation executes in under 50ms on cold cache and sub-10ms on warm cache.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/graph/redstring_bridge.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Redstring Entity and Relationship Extraction
```gherkin
Given a project repository with accepted PRDs, tasks, and ADRs
When the extractor parses the repository frontmatter
Then a Redstring InMemoryGraphStore is populated with typed entities and relationships
And graph queries for dependencies return valid topological neighbors
```

### Scenario 2: Content-Addressed Graph Caching
```gherkin
Given a compiled Redstring graph cached to disk at ".specops/cache/graph.json"
When no markdown files have been modified
Then compiling the graph loads from the cache snapshot in under 50 milliseconds
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary directed acyclic graph of task dependencies, graph serialization and deserialization preserves all topological paths and neighbor sets.
