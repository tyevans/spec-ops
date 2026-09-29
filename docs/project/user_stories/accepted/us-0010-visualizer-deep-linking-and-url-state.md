---
id: '0010'
title: Visualizer Deep Linking, URL State Synchronization, and Shareable Entity Permalinks
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-VIS-03
governing_prd: PRD-0001
---

# US-0010 — Visualizer Deep Linking, URL State Synchronization, and Shareable Entity Permalinks

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** engineering lead, system architect, or product manager,  
**I want** the SpecOps visualizer to synchronize its active view tab, search queries, faceted filters, and open entity drawer in the browser URL hash fragment,  
**So that** I can share direct permalinks to specific visualizer views, filtered backlog states, or individual tasks and ADRs with teammates and autonomous agents, and utilize standard browser back and forward history buttons without full page reloads.

## Acceptance Criteria

### Scenario 1: Direct Tab Permalinking via URL Hash
```gherkin
Given the standalone visualizer is loaded in a browser
When the user accesses a URL containing a tab hash:
  | URL Hash            | Expected Tab View    |
  | #tab=graph          | Relationship Graph   |
  | #tab=gantt          | Gantt & Timeline     |
  | #tab=kanban         | Kanban Pipeline      |
  | #tab=prds           | PRDs & Features      |
  | #tab=adrs           | ADR Architecture     |
  | #tab=personas       | Personas & Stories   |
Then the corresponding dashboard tab is activated immediately on mount
And the active tab button displays the highlighted state
And no full page reload or network request occurs.
```

### Scenario 2: Deep Linking to Specific Entity Detail Drawer
```gherkin
Given a project repository with documented tasks, ADRs, PRDs, and personas
When the user opens the visualizer with a deep-linked entity identifier in the URL:
  | URL Hash                   | Expected Entity | Expected Type |
  | #entity=TASK-0013          | TASK-0013       | TASK          |
  | #tab=adrs&entity=ADR-0002  | ADR-0002        | ADR           |
  | #entity=PRD-0001           | PRD-0001        | PRD           |
Then the visualizer activates the requested tab or defaults to the entity's primary context
And the detail drawer opens automatically with the entity title, status, and file path
And the background view renders behind the drawer without error.
```

### Scenario 3: Faceted Filter and Search Query State Synchronization
```gherkin
Given the user navigates to the "Kanban Pipeline" or "ADR Architecture" tab
When the user modifies faceted filter controls:
  | Filter Action              | Parameter   | Example Value    |
  | Enter search query         | q           | rescue           |
  | Filter by status           | status      | Refined          |
  | Filter by bounded context  | bc          | core             |
  | Toggle completion filter   | hideDone    | true             |
Then the URL hash updates reactively to reflect the active filter state
And reloading or sharing the URL reproduces the exact filtered view and matching entity cards.
```

### Scenario 4: Browser History Traversal (Back / Forward)
```gherkin
Given the user has switched tabs from "Relationship Graph" to "Kanban Pipeline" and opened "TASK-0013"
When the user clicks the browser "Back" button
Then the detail drawer closes while preserving the "Kanban Pipeline" view
And clicking the browser "Back" button again returns to the "Relationship Graph"
And clicking "Forward" re-applies each navigation transition without reloading the page.
```

### Scenario 5: Permalinking and Canvas Node Focal Zooming
```gherkin
Given the user opens a deep link targeting an entity on the "Relationship Graph" canvas:
  | Deep Link Hash              | Target Entity |
  | #tab=graph&entity=TASK-0001  | TASK-0001     |
When the canvas simulation initializes
Then the camera viewport pans and centers smoothly onto the target node
And the node is highlighted with an active glowing halo
And clicking "Copy Deep Link" in the open drawer copies the canonical permalink to the clipboard.
```
