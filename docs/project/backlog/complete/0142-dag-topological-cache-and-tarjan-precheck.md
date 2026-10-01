---
id: '0142'
title: Incremental DAG Topological Cache and Fast Tarjan Cycle Pre-Check
status: Complete
dependencies:
- TASK-0058
- TASK-0128
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0017
governing_prds:
- PRD-0005
governing_stories:
- US-0016
- US-0058
target_bc: core
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T11:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0142: Incremental DAG Topological Cache and Fast Tarjan Cycle Pre-Check

## Summary
Implement the incremental DAG topological cache and sub-millisecond cycle pre-check engine (`src/spec_ops/core/dag_cache.py`). Fulfilling ADR-0017 and PRD-0005, this engine maintains an in-memory and disk-cached topological tiering structure (`.specops/cache/topology.json`) so that adding a dependency candidate to a task triggers an immediate, zero-latency cycle pre-check without full graph re-computations.

## Problem Statement & Context
As task backlogs scale beyond hundreds of items, evaluating task dependencies with repeated full-graph Tarjan strongly connected components (SCC) and Kahn topological sorting introduces latency during CLI execution. ADR-0017 mandates content-addressed graph caching and fast topological pre-checks to maintain instantaneous queue operations (<10ms).

## Key Requirements & Scope
1. **Incremental DAG Cache (`src/spec_ops/core/dag_cache.py`)**:
   - Persists topological execution tiers and transitive reachability matrices in `.specops/cache/topology.json`.
   - Validates cache validity using SHA-256 fingerprinting of backlog task files.
2. **Fast Cycle Pre-Check (`can_add_dependency`)**:
   - Evaluates whether adding `source -> target` introduces a cyclic dependency using cached reachability sets in <1ms.
   - Raises domain violation errors with exact cyclic path details before writing to disk.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: DAG cache module in `src/spec_ops/core/dag_cache.py` must stay strictly under 400 lines (ADR-0002).
- **Acyclic Graph Invariant (ADR-0017)**: The backlog execution graph must strictly remain a directed acyclic graph (DAG) at all times.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/core/dag_cache.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Fast cycle pre-check rejecting circular dependencies
```gherkin
Given a cached task dependency DAG where "TASK-0002" depends on "TASK-0001"
When a command attempts to add "TASK-0001" as a dependency of "TASK-0002"
Then the cycle pre-check rejects the dependency in under 5 milliseconds
And reports the exact cyclic path "TASK-0001 -> TASK-0002 -> TASK-0001"
```

### Scenario 2: Preserving cached topological execution tiers
```gherkin
Given an unmodified repository with valid topological cache
When the queue engine requests execution tiers
Then tiers are retrieved directly from cache without full repository graph parsing
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary acyclic graph, the incremental cycle pre-check allows all valid edge additions and rejects all backwards cyclic edge insertions deterministically.
