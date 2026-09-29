---
id: '0059'
title: 'Architectural Spike: Tarjan Strongly Connected Components (SCC) Cycle Resolution, Topological Sorting, and Blast-Radius Traversal'
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0059
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0007
  - ADR-0009
governing_prds:
  - PRD-0005
governing_stories:
  - US-0060
  - US-0063
target_bc: core
---

# TASK-0060: Architectural Spike: Tarjan Strongly Connected Components (SCC) Cycle Resolution, Topological Sorting, and Blast-Radius Traversal

## Summary
Conduct a targeted architectural spike to evaluate, benchmark, and mathematically formalize cycle detection, topological sorting, and blast-radius traversal across cyclic directed multi-graphs. Evaluate Tarjan's Strongly Connected Components (SCC) algorithm versus Kahn's algorithm and Johnson's elementary cycle enumeration for dependency graphs up to 5,000 nodes. Establish algorithmic strategies to isolate strongly connected cyclic subgraphs, output exact node cycle paths with remediation suggestions, compute deterministic topological execution tiers for acyclic components, and calculate upstream/downstream blast radius transitive closures in under 10 milliseconds.

## Problem Statement & Context
Complex project backlogs and specification networks frequently develop accidental dependency cycles (e.g. Task A requires Task B, which transitively requires Task A, or circular dependencies between PRDs and User Stories). Standard topological sorting algorithms fail catastrophically on cyclic graphs, causing queue freezes and infinite loops in autonomous dispatchers. SpecOps needs a mathematically sound, performant graph topology engine that pinpoints cycles with exact cycle path traces, isolates cycles without blocking independent task clusters, and calculates downstream blast radius when specifications or ADRs are superseded.

## User Stories & Scenarios Satisfied
- **US-0060: Deterministic Graph Cycle Detection, Topological Sorting, and Dependency Depth Extraction**
  - *Scenario: Computing valid topological task execution order for a multi-stage backlog*
  - *Scenario: Detecting a multi-node circular dependency with exact cycle path traceback*
  - *Scenario: Catching cross-entity circular reference traps between PRDs and User Stories*
- **US-0063: Terminal Graph Inspection, Reachability Pathfinding, and Blast-Radius Traversal**
  - *Scenario: Inspecting an entity's direct graph neighborhood and lineage*
  - *Scenario: Finding the shortest traceability path between a customer persona and a git commit*
  - *Scenario: Calculating downstream blast radius of an ADR before superseding it*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Spike prototype algorithms in `src/spec_ops/core/spikes/topology_spike.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly synthesized directed graphs (both DAGs and cyclic digraphs) assert that Tarjan SCC correctly partitions the graph such that any subgraph with SCC size > 1 is a cycle, and the condensation graph is strictly an acyclic DAG admitting a valid topological sort.
- **Mutmut Mutation Scope**: Tarjan SCC traversal and cycle extraction in `src/spec_ops/core/spikes/topology_spike.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Spike benchmarks cycle detection across a 5,000-node graph with 10 injected circular loops, detecting 100% of cycles in under 15 milliseconds.
2. Prototype returns deterministic, human-readable cycle path tracebacks (e.g. `TASK-0010 -> TASK-0015 -> TASK-0020 -> TASK-0010`) identifying the exact feedback edges.
3. Topological sort produces valid execution tiers for all acyclic nodes, isolating cyclic components into a quarantined deadlock partition.
4. Blast radius calculation computes the complete transitive downstream dependent set of any entity in under 5ms on a 1,000-node graph.
5. Algorithmic trade-offs, benchmarks, and formal mathematical proofs are compiled into `docs/project/adrs/proposed/adr-0011-deterministic-dag-topology-and-cycle-resolution.md`.
