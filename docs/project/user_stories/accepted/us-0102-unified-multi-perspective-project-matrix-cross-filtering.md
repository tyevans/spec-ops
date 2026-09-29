---
id: '0102'
title: Unified Multi-Perspective Project Matrix with Relational Cross-Filtering
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-VIS-02
governing_prd: PRD-0005
---

# US-0102 — Unified Multi-Perspective Project Matrix with Relational Cross-Filtering

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** engineering lead,
  - **I want** to switch between specialized project perspectives (Relationship Graph, Gantt Timeline, Kanban Pipeline, PRDs & Features, ADR Architecture, and Personas & Stories Studio) with bidirectional relational cross-filtering,
  - **So that** my hybrid team can conduct high-velocity daily standups, milestone roadmap reviews, and architectural impact triages directly from version-locked git ground truth.

## Acceptance Criteria

```gherkin
Scenario: Seamless Multi-Tab Dashboard Navigation Shell
Given the standalone visualizer is open in a browser
When Jordan clicks any navigation tab in the top tab bar:
| Tab Name             | Target Identifier | Expected Active View   |
| Relationship Graph   | graph             | Canvas 2D simulation   |
| Gantt & Timeline     | gantt             | Horizon progress bars  |
| Kanban Board         | kanban            | 3-column backlog lanes |
| PRDs & Features      | prds              | PRD outcome matrix     |
| ADR Architecture     | adrs              | ADR governance radar   |
| Personas & Stories   | personas          | Persona & Story studio |
Then the active view switches immediately without page reload
And graph simulation controls are displayed only on the "graph" tab
And the active tab button receives the highlighted styling class.
```
```gherkin
Scenario: Cross-Entity Relational Pivoting from PRDs and ADRs to Backlog Tasks
Given Jordan is reviewing an architectural record on the "ADR Architecture" tab
When Jordan clicks the "📋 View Tasks" button on "ADR-0002"
Then the visualizer automatically transitions to the "Kanban Board" tab
And an active filter chip appears displaying "Linked to: ADR-0002" with a dismissal button
And the Kanban lanes display only backlog tasks that cite "ADR-0002" in their governing ADR metadata
And clicking the dismissal button clears the filter and restores the full task board.
```
```gherkin
Scenario: Delivery Horizon and Bounded Context Grouping in Gantt Timeline
Given Jordan is viewing the "Gantt & Timeline" tab
When Jordan toggles the grouping control between "Release" and "Bounded Context"
Then deliverable rows are regrouped dynamically:
| Grouping Mode    | Group Headers Example                        |
| Release          | Release M1, Release M2, Unscheduled         |
| Bounded Context  | BC: core, BC: visualizer, BC: reporting      |
And each group header displays an aggregate progress completion bar and percentage
And clicking any task row opens the full detail drawer for that deliverable.
```
```gherkin
Scenario: Real-Time Faceted Search and Bounded Context Isolation
Given the visualizer is active on any dashboard tab
When Jordan enters a search query "health" or selects bounded context "core" from the filter bar
Then matching items are filtered reactively across cards, lanes, and canvas nodes within 50ms
And non-matching items are hidden from the active view.
```

## Rationale & Compelling Value
Delivers complete bidirectional situational awareness. Clicking an ADR or PRD instantly filters the entire backlog to relevant engineering tasks, eliminating manual cross-referencing.

---
