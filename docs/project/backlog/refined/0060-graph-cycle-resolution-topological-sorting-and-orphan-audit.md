---
id: '0060'
title: Deterministic Graph Cycle Resolution, Topological Sorting, Reachability Pathfinding,
  and Orphan Work Item Audit
status: Refined
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
- US-0063
- US-0016
- US-0021
target_bc: core
claimed_by: worker-3
branch: feat/0060-deterministic-graph-cycle-resolution--to
---

# TASK-0060: Deterministic Graph Cycle Resolution, Topological Sorting, Reachability Pathfinding, and Orphan Work Item Audit

## Summary
Implement production CLI commands and graph algorithms for deterministic cycle detection (`spec-ops graph cycles [--format json]`), topological backlog execution sorting (`spec-ops graph sort`), terminal reachability pathfinding (`spec-ops graph path --from <src> --to <dst>`), downstream blast-radius analysis (`spec-ops graph blast-radius <entity>`), full bidirectional graph traceability validation (`spec-ops graph audit`), and autonomous backlog bottleneck/deadlock detection. Isolate cyclic dependency traps, detect orphaned tasks or stories lacking parent PRDs, calculate critical-path execution depth, and pinpoint high-fanout dependency choke points.

## Problem Statement & Context
Engineering leads and autonomous coding agents need complete visibility into repository relationship topology. Accidental cycles in task prerequisites stall agent dispatchers; unanchored tasks and orphaned specifications silently slip into branches without connecting to customer personas or business outcomes; and modifying core architectural decision records or foundational tasks carries unknown blast radii. SpecOps requires a unified graph analysis suite to detect cycles, audit bidirectional traceability, and calculate blast radii before risky refactorings or supersessions.

## User Stories & Scenarios Satisfied
- **US-0060: Deterministic Graph Cycle Detection, Topological Sorting, and Dependency Depth Extraction**
  - *Scenario: Computing valid topological task execution order for a multi-stage backlog*
  - *Scenario: Detecting a multi-node circular dependency with exact cycle path traceback*
  - *Scenario: Catching cross-entity circular reference traps between PRDs and User Stories*
- **US-0063: Terminal Graph Inspection, Reachability Pathfinding, and Blast-Radius Traversal**
  - *Scenario: Inspecting an entity's direct graph neighborhood and lineage*
  - *Scenario: Finding the shortest traceability path between a customer persona and a git commit*
  - *Scenario: Calculating downstream blast radius of an ADR before superseding it*
- **US-0016: Full Bidirectional Graph Traceability and Orphan Work Item Audit**
  - *Scenario: Clean repository passing bidirectional graph verification*
  - *Scenario: Detecting an orphaned task with a non-existent story link*
  - *Scenario: Detecting cyclical task dependencies in the backlog graph*
- **US-0021: Autonomous Backlog Bottleneck and Critical Path Deadlock Detection**
  - *Scenario: Identifying High-Fanout Dependency Choke Points*
  - *Scenario: Detecting Circular Dependency Deadlocks*
  - *Scenario: Pre-empting Ready Buffer Starvation*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Graph topology analysis in `src/spec_ops/core/topology.py`, pathfinding in `src/spec_ops/core/pathfinder.py`, and audit commands in `src/spec_ops/core/graph_audit.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that for any generated DAG, topological sort produces an ordering where for every directed edge (u, v), u appears before v; and for any cyclic graph, `spec-ops graph cycles` always reports non-empty cycles and exits with code 1.
- **Mutmut Mutation Scope**: Tarjan cycle detection and reachability search in `src/spec_ops/core/topology.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops graph cycles` on a valid repository exits with code 0; on a circular dependency, exits with code 1 and prints the exact cycle chain (e.g. `TASK-0010 -> TASK-0015 -> TASK-0020 -> TASK-0010`) with remediation suggestions.
2. Executing `spec-ops graph sort` outputs a valid topological execution sequence partitioned into parallel execution stages.
3. Executing `spec-ops graph path --from PERSONA-0001 --to COMMIT-SHA` prints the shortest unbroken traceability lineage chain across stories, PRDs, and tasks.
4. Executing `spec-ops graph blast-radius ADR-0002` lists all directly and transitively dependent ADRs, tasks, and stories affected by modification.
5. Executing `spec-ops graph audit` flags orphan tasks lacking story links, orphan stories lacking PRD links, and high-fanout bottleneck choke points.
6. All scenarios verified via public frontdoors using `pytest-bdd` without mock backdoors (ADR-0003, ADR-0006).
