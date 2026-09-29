---
id: '0060'
title: Deterministic Graph Cycle Detection, Topological Sorting, and Dependency Depth Extraction
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-CORE-02
governing_prd: PRD-0005
---

# US-0060 — Deterministic Graph Cycle Detection, Topological Sorting, and Dependency Depth Extraction

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** AI-native engineering lead,
  - **I want** the SpecOps core graph engine to compute topological execution orders and detect cyclical dependencies using Tarjan's strongly connected components algorithm,
  - **So that** circular task dependency deadlocks and recursive entity links are caught with exact cycle-path traces and cycle-breaking suggestions before work is scheduled or refined.

## Acceptance Criteria

```gherkin
Scenario: Computing valid topological task execution order for a multi-stage backlog
Given a backlog with tasks:
| id        | dependencies        |
| TASK-0001 |                     |
| TASK-0002 | [TASK-0001]         |
| TASK-0003 | [TASK-0001]         |
| TASK-0004 | [TASK-0002, TASK-0003] |
When the lead runs "spec-ops graph order --type task"
Then the command exits with code 0
And outputs the deterministic topological sequence:
"""
1. TASK-0001 (depth: 0)
2. TASK-0002 (depth: 1)
3. TASK-0003 (depth: 1)
4. TASK-0004 (depth: 2)
"""
And identifies the critical path depth as 2.
```
```gherkin
Scenario: Detecting a multi-node circular dependency with exact cycle path traceback
Given task "TASK-0010" depends on "TASK-0011"
And task "TASK-0011" depends on "TASK-0012"
And task "TASK-0012" depends on "TASK-0010"
When the lead runs "spec-ops graph order --type task"
Then the command exits with code 1
And reports "Cyclic Backlog Dependency Detected: Strongly Connected Component of size 3"
And prints the directed cycle path: "TASK-0010 -> TASK-0011 -> TASK-0012 -> TASK-0010"
And recommends: "Break cycle by removing dependency from TASK-0012 to TASK-0010".
```
```gherkin
Scenario: Catching cross-entity circular reference traps between PRDs and User Stories
Given PRD "PRD-0002" claims implementing stories "[US-0015]"
And User Story "US-0015" specifies governing PRD "PRD-0003"
And PRD "PRD-0003" claims implementing stories "[US-0015]"
When the lead runs "spec-ops trace --verify"
Then the command exits with code 1
And reports "Inconsistent Traceability Boundary: US-0015 is claimed by PRD-0002 but specifies PRD-0003".
-
```

## Rationale & Compelling Value
- **Adoption**: Eliminates dependency deadlocks that confuse autonomous coding agents and paralyze sprint progress.
  - **Regular Usage**: Automatically invoked during backlog curation (`spec-ops curate`) and agent claiming (`spec-ops worker`) to ensure agents only pull unblocked tasks.
  - **Compelling Value**: SaaS tools (Jira, Linear) allow users to arbitrarily link tickets as "blocks / is blocked by" without cycle verification, leading to deadlock loops. SpecOps enforces mathematical DAG acyclicity directly at the git level.

---
