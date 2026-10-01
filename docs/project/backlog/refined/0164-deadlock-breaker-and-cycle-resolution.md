---
id: '0164'
title: Multi-Agent Task Dependency Graph Deadlock Resolver and Cycle Auto-Break Engine
status: Refined
dependencies:
- TASK-0060
- TASK-0128
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0017
governing_prds:
- PRD-0005
- PRD-0006
governing_stories:
- US-0089
- US-0117
target_bc: core
---

# TASK-0164: Multi-Agent Task Dependency Graph Deadlock Resolver and Cycle Auto-Break Engine

## Summary
Implement an autonomous dependency deadlock resolver and cycle breaker for the task dependency graph (`src/spec_ops/core/deadlock_breaker.py`). Governed by ADR-0017 and PRD-0005, this engine detects cyclic dependencies among backlog tasks and computes minimal edge removal recommendations to restore a clean Directed Acyclic Graph (DAG) without unresolvable deadlocks (`spec-ops graph deadlock`).

## Problem Statement & Context
As multiple autonomous agents and human architects create and link backlog tasks, circular dependency cycles can inadvertently form (e.g. Task A depends on Task B which depends on Task A). Circular dependencies halt queue progression because neither task can ever satisfy the Definition of Ready. An automated cycle breaker analyzes Tarjan strongly connected components (SCC) and provides deterministic resolution paths.

## Key Requirements & Scope
1. **Deadlock Breaker Engine (`src/spec_ops/core/deadlock_breaker.py`)**:
   - Analyzes directed dependency graphs across all backlog tasks.
   - Detects all simple cycles and Strongly Connected Components using Tarjan's algorithm.
   - Computes minimum feedback arc set heuristics to identify the optimal dependency edges to remove.
   - Outputs actionable resolution plans detailing which dependency declarations to prune.
2. **Deadlock Resolution CLI (`spec-ops graph deadlock [--resolve] [--json] [--dry-run]`)**:
   - Displays detected cycles and proposed edge cut recommendations.
   - Exits with code 0 if the graph is acyclic, or code 1 if deadlocks exist.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Module in `src/spec_ops/core/deadlock_breaker.py` must stay strictly under 400 lines (ADR-0002).
- **Deterministic DAG Topology (ADR-0017)**: Preserves deterministic topological ordering.
- **Mutation Testing Scope**: Target module `src/spec_ops/core/deadlock_breaker.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Detecting circular task dependencies and proposing edge breaks
```gherkin
Given a backlog task graph containing a cyclic dependency between Task A and Task B
When the deadlock breaker analyzes the graph
Then the circular dependency cycle is identified
And a minimal edge removal recommendation is generated
And the command terminates with exit code 1
```

### Scenario 2: Verifying an acyclic dependency graph
```gherkin
Given a backlog task graph with valid topological ordering and zero cycles
When the deadlock breaker analyzes the graph
Then the graph is confirmed acyclic
And exits with code 0
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary directed graph, applying the computed edge removal set guarantees that the resulting graph contains zero cycles.
