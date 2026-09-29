---
id: '0063'
title: Terminal Graph Inspection, Reachability Pathfinding, and Blast-Radius Traversal
status: Accepted
created: 2026-09-29
persona: Riley (The Human IC Developer)
feature: FEAT-CORE-05
governing_prd: PRD-0005
---

# US-0063 — Terminal Graph Inspection, Reachability Pathfinding, and Blast-Radius Traversal

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As a** human IC developer,
  - **I want** to query the relational graph directly from the CLI using `spec-ops graph inspect` and `spec-ops graph path`,
  - **So that** I can trace shortest paths between personas, stories, tasks, and commits, and inspect upstream/downstream blast radius before modifying code or architectural decisions.

## Acceptance Criteria

```gherkin
Scenario: Inspecting an entity's direct graph neighborhood and lineage
Given a repository where task "TASK-0042" is governed by "ADR-0003", implements "US-0020", and targets bounded context "invariants"
When the developer runs "spec-ops graph inspect TASK-0042"
Then the command outputs an ASCII entity card displaying:
| Field            | Value                         |
| Entity ID        | TASK-0042                     |
| Type             | Task (Refined)                |
| Target BC        | invariants                    |
| Governing ADRs   | ADR-0003                      |
| Governing Story  | US-0020                       |
| Persona Lineage  | Jordan (via US-0020)          |
And lists all 1st-degree upstream dependencies and downstream dependents.
```
```gherkin
Scenario: Finding the shortest traceability path between a customer persona and a git commit
Given persona "taylor" desires story "US-0046"
And story "US-0046" specifies PRD "PRD-0001"
And PRD "PRD-0001" is implemented by task "TASK-0046"
And commit "a1b2c3d" contains git message "feat: uat matrix (TASK-0046)"
When the developer runs "spec-ops graph path --from persona:taylor --to commit:a1b2c3d"
Then the command exits with code 0
And prints the directed shortest path:
"""
persona:taylor
└──[desires]──> story:US-0046
└──[implements]──> task:TASK-0046
└──[committed_in]──> commit:a1b2c3d
Path length: 3 hops.
"""
```
```gherkin
Scenario: Calculating downstream blast radius of an ADR before superseding it
Given ADR "ADR-0003" governs 8 active backlog tasks across 3 bounded contexts
When the developer runs "spec-ops graph blast-radius ADR-0003"
Then the command outputs:
"""
Blast Radius for ADR-0003:
- 8 governing tasks: [TASK-0002, TASK-0020, TASK-0042, ...]
- 3 affected bounded contexts: [core, invariants, visualizer]
- 2 active pull requests: [#104, #112]
Total Downstream Impact: HIGH (13 nodes affected)
"""
-
```

## Rationale & Compelling Value
- **Adoption**: Empowers developers to quickly answer "Why does this requirement exist?" or "What breaks if I change this decision?" right from their terminal without opening a browser.
  - **Regular Usage**: Used daily during PR reviews, architectural spike exploration, and commit message authoring.
  - **Compelling Value**: Replaces hours of searching through disconnected Jira boards, Confluence pages, and GitHub PR histories with a single instant graph query on local git specifications.

---
