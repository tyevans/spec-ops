---
id: '0048'
title: Persona-to-Commit Bidirectional Traceability Matrix and Coverage Auditor
status: Accepted
created: 2026-09-29
persona: Taylor (The Product Manager)
feature: FEAT-VIS-04
governing_prd: PRD-0003
---

# US-0048 — Persona-to-Commit Bidirectional Traceability Matrix and Coverage Auditor

## Governing PRD
- [`PRD-0003: Product Discovery, Web PRD Studio & Living UAT Verification`](../../product/accepted/prd-0003-product-discovery-web-prd-studio-and-living-uat-verification.md)

## User Story

**As an** product manager,  
**I want** an interactive Customer Traceability Matrix that visualizes the unbroken lineage from Persona needs down to PRDs, Gherkin stories, backlog tasks, pull requests, and git commits,  
**So that** I can answer stakeholder status queries instantly, identify orphaned requirements, and audit persona coverage across active development.

## Acceptance Criteria

```gherkin
Scenario: Inspecting Full Lineage for a Customer Persona
Given documented personas in "PERSONAS.md" and linked stories across the backlog
When Taylor selects "Persona: Taylor" in the visualizer Traceability Matrix
Then the interface renders a multi-column lineage view:
  | Persona | PRD      | User Story | Backlog Task | Git Commit | Status   |
  | Taylor  | PRD-0001 | US-0006    | TASK-0008    | abc1234    | Complete |
  | Taylor  | PRD-0001 | US-0009    | TASK-0013    | def5678    | Complete |
And clicking any node in the lineage chain highlights its connections across the entire project graph.
```

```gherkin
Scenario: Auditing Persona Coverage and Highlighting Neglected Customer Segments
Given the project has active tasks in "proposed/" and "refined/"
When Taylor executes "spec-ops stats --persona-coverage" or views the Persona Studio
Then a coverage distribution report is displayed showing task allocation per persona
And warns when a persona has 0 active stories in the current milestone
And flags any backlog task lacking a governing user story or persona lineage as an "Orphan Task".
```

```gherkin
Scenario: Instant Stakeholder Query Resolution via Shareable Permalinks
Given Taylor receives an inquiry from leadership asking about progress on "Living 2D Graph Visualizer"
When Taylor filters the Traceability Matrix by "FEAT-VIS-01"
And clicks "Copy Shareable Link"
Then the clipboard receives a deep link permalink with URL state "#tab=prds&entity=PRD-0001&filter=FEAT-VIS-01"
And recipient opening the URL sees the exact filtered lineage and delivery progress without logging in.
```

## Rationale & Compelling Value
Uncovers neglected personas and ensures every engineering dollar maps directly to documented customer value with instant permalinks.
