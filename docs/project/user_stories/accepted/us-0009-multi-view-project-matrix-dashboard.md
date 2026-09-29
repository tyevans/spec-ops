---
id: '0009'
title: Multi-View Project Matrix Dashboard with Gantt, Kanban, PRD & ADR Exploration
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-VIS-02
governing_prd: PRD-0001
---

# US-0009 — Multi-View Project Matrix Dashboard with Gantt, Kanban, PRD & ADR Exploration

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** engineering lead or system architect,  
**I want** to switch between specialized dashboard views (2D Relationship Graph, Gantt Timeline, Kanban Pipeline, PRD Matrix, ADR Radar, and Personas & Stories Studio) with live faceted filtering,  
**So that** I can inspect delivery horizons, triage backlog states, explore architectural decisions, and query relational dependencies (e.g., tasks implementing a specific PRD or ADR) without external project management tooling.

## Acceptance Criteria

### Scenario 1: Multi-Tab Navigation Shell
```gherkin
Given the standalone visualizer is open in a browser
When the user clicks the top navigation tabs
Then the view switches seamlessly between:
  | Tab Name             | Identifier     |
  | Relationship Graph   | graph          |
  | Gantt & Timeline     | gantt          |
  | Kanban Pipeline      | kanban         |
  | PRDs & Features      | prds           |
  | ADR Architecture     | adrs           |
  | Personas & Stories   | personas       |
And the active tab is highlighted with zero page reloads.
```

### Scenario 2: Gantt Chart and Delivery Horizons
```gherkin
Given the user navigates to the "Gantt & Timeline" tab
When the delivery timeline renders
Then deliverables are displayed with status-coded progress bars
And the user can toggle grouping between "Release / Milestone" and "Bounded Context"
And checking "Hide Done" filters out completed tasks.
```

### Scenario 3: Kanban Backlog Pipeline
```gherkin
Given the user navigates to the "Kanban Pipeline" tab
When the board renders
Then tasks are sorted into 3 columns: "Proposed", "Refined", and "Complete"
And each task card displays its canonical ID, title, target bounded context, and linked PR/commit counts
And clicking any task card opens its rich detail drawer.
```

### Scenario 4: PRD & ADR Browsing with Relational Filtering
```gherkin
Given the user navigates to "PRDs & Features" or "ADR Architecture"
When the user inspects an entity
Then all implementing backlog tasks are listed with interactive pills
And clicking an implementing task pill opens that task's specification drawer
And the search input filters entities in real time by title, ID, or domain.
```
