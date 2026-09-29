---
id: '0074'
title: Deterministic Multi-Criteria Priority Re-Ranking and Topological Backlog Ordering
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-BACK-02
governing_prd: PRD-0005
---

# US-0074 — Deterministic Multi-Criteria Priority Re-Ranking and Topological Backlog Ordering

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** agentic systems architect,
  - **I want** to execute `spec-ops backlog reorder` to deterministically re-rank `PRIORITY.md` using multi-criteria topological sorting,
  - **So that** foundational tasks and high-fanout blocking dependencies are always prioritized above downstream work, eliminating priority inversion anomalies and manual sorting toil.

## Acceptance Criteria

```gherkin
Scenario: Topological Re-ordering to Resolve Priority Inversion
Given task "TASK-0005" depends on task "TASK-0012"
And in "PRIORITY.md", "TASK-0005" is listed at position 4 while "TASK-0012" is listed at position 15
When the architect runs "spec-ops backlog reorder --topological"
Then the re-ranking algorithm detects the priority inversion
And reorders "PRIORITY.md" so that prerequisite "TASK-0012" strictly precedes dependent "TASK-0005"
And verifies 0 circular dependency cycles before writing the updated index.
```
```gherkin
Scenario: Multi-Criteria Weighted Priority Scoring (Milestone, Blocker Count, Impact)
Given proposed task "TASK-0040" blocks 5 downstream tasks in "Milestone 2"
And proposed task "TASK-0041" blocks 0 downstream tasks in "Milestone 3"
When the architect runs "spec-ops backlog reorder --by-weights"
Then "TASK-0040" is assigned a higher priority rank than "TASK-0041" based on downstream fan-out weight and target milestone deadline
And "PRIORITY.md" reflects the updated sequential ordering.
```
```gherkin
Scenario: Respecting Architect Pin Overrides during Reordering
Given task "TASK-0008" contains "priority_pin: 1" in its YAML frontmatter
When the architect runs "spec-ops backlog reorder"
Then "TASK-0008" remains locked at position 1 in "PRIORITY.md"
And all other unpinned tasks are sorted topologically around it without violating prerequisite constraints.
-
```

## Rationale & Compelling Value
- **Adoption**: Enables teams importing legacy backlogs to instantly generate a mathematically sound, dependency-validated execution queue without manual drag-and-drop.
  - **Regular Usage**: Executed whenever new PRDs are decomposed into vertical slices or architectural spikes are scheduled.
  - **Compelling Value**: Completely eliminates "worker starvation" caused by agents claiming tasks whose dependencies are buried hundreds of lines down the backlog.

---
