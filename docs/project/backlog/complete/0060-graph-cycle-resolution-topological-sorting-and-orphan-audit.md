---
id: '0060'
title: Deterministic Graph Cycle Resolution and Topological Sorting Engine
status: Complete
dependencies:
- TASK-0059
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0060
target_bc: core
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0060: Deterministic Graph Cycle Resolution and Topological Sorting Engine

## Summary
Implement production CLI commands and graph algorithms for deterministic cycle detection (`spec-ops graph cycles [--format json]`) and topological backlog execution sorting (`spec-ops graph sort`). Isolate cyclic dependency traps, calculate critical-path execution depth, and compute valid topological execution stages.

## Problem Statement & Context
Engineering leads and autonomous coding agents need complete visibility into repository relationship topology. Accidental cycles in task prerequisites stall agent dispatchers and corrupt dependency graphs. SpecOps requires a deterministic graph analysis engine to detect cycles with exact cycle path tracebacks and partition backlog execution into parallel dependency tiers.

## User Stories & Scenarios Satisfied
- **US-0060: Deterministic Graph Cycle Detection, Topological Sorting, and Dependency Depth Extraction**
  - *Scenario: Computing valid topological task execution order for a multi-stage backlog*
  - *Scenario: Detecting a multi-node circular dependency with exact cycle path traceback*
  - *Scenario: Catching cross-entity circular reference traps between PRDs and User Stories*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Graph topology analysis in `src/spec_ops/core/topology.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that for any generated DAG, topological sort produces an ordering where for every directed edge (u, v), u appears before v; and for any cyclic graph, `spec-ops graph cycles` always reports non-empty cycles and exits with code 1.
- **Mutmut Mutation Scope**: Tarjan cycle detection and topological sorting in `src/spec_ops/core/topology.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops graph cycles` on a valid repository exits with code 0; on a circular dependency, exits with code 1 and prints the exact cycle chain (e.g. `TASK-0010 -> TASK-0015 -> TASK-0020 -> TASK-0010`) with remediation suggestions.
2. Executing `spec-ops graph sort` outputs a valid topological execution sequence partitioned into parallel execution stages.
3. All scenarios verified via public frontdoors using `pytest-bdd` without mock backdoors (ADR-0003, ADR-0006).
