---
id: 0087
title: Terminal Graph Inspection, Reachability Pathfinding, and Blast-Radius Traversal
status: Refined
dependencies:
- TASK-0060
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
- US-0063
target_bc: core
---

# TASK-0087: Terminal Graph Inspection, Reachability Pathfinding, and Blast-Radius Traversal

## Summary
Implement CLI commands for interactive entity graph inspection (`spec-ops graph inspect <entity>`), shortest-path reachability pathfinding (`spec-ops graph path --from <src> --to <dst>`), and downstream blast-radius analysis (`spec-ops graph blast-radius <entity>`) directly from the terminal without external browser dependencies.

## Problem Statement & Context
Developers and architects navigating complex PMaC projects need immediate answers to "Why does this requirement exist?", "What is the unbroken traceability chain from this persona to this commit?", and "What breaks if I modify this ADR or foundational task?" Without terminal-native inspection and pathfinding tools, developers must open browser-based visualizers or manually parse multiple markdown specifications.

## User Stories & Scenarios Satisfied
- **US-0063: Terminal Graph Inspection, Reachability Pathfinding, and Blast-Radius Traversal**
  - *Scenario: Inspecting an entity's direct graph neighborhood and lineage*
  - *Scenario: Finding the shortest traceability path between a customer persona and a git commit*
  - *Scenario: Calculating downstream blast radius of an ADR before superseding it*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Graph pathfinding in `src/spec_ops/core/pathfinder.py` and CLI inspection in `src/spec_ops/cli/graph_handler.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly generated acyclic and cyclic graphs assert that the shortest path algorithm terminates with the minimal hop count and returns `None` if and only if no directed path connects source to destination.
- **Mutmut Mutation Scope**: Breadth-first and Dijkstra reachability search in `src/spec_ops/core/pathfinder.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops graph inspect <entity>` outputs an entity card with type, target bounded context, governing ADRs/stories, persona lineage, and 1st-degree upstream/downstream connections.
2. Executing `spec-ops graph path --from <src> --to <dst>` outputs the directed shortest path chain with hop count and relationship labels.
3. Executing `spec-ops graph blast-radius <entity>` lists all directly and transitively dependent ADRs, tasks, and stories affected by modification.
4. All scenarios verified via public frontdoors using `pytest-bdd` without mock backdoors (ADR-0003, ADR-0006).
