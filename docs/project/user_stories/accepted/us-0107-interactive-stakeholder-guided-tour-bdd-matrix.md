---
id: '0107'
title: Interactive Non-Technical Stakeholder Guided Tour and BDD Acceptance Matrix
status: Accepted
created: 2026-09-29
persona: Taylor (The Product Manager & Technical Writer)
feature: FEAT-VIS-07
governing_prd: PRD-0005
---

# US-0107 — Interactive Non-Technical Stakeholder Guided Tour and BDD Acceptance Matrix

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As a** product manager,
  - **I want** an interactive onboarding guided tour and executable BDD acceptance matrix in the visualizer,
  - **So that** non-technical business partners, customer representatives, and compliance auditors can verify customer-facing outcomes, explore executable Gherkin scenarios against live test results, and sign off on milestone deliverables without reading raw code.

## Acceptance Criteria

```gherkin
Scenario: First-Time Stakeholder Interactive Onboarding Walkthrough
Given a non-technical stakeholder opens the visualizer for the first time
When the stakeholder clicks "Take Guided Tour" in the top navigation
Then a step-by-step interactive spotlight overlays the screen explaining:
1. The core philosophy of Project Management as Code (PMaC)
2. How Personas connect to PRDs, Stories, and Backlog Tasks
3. How to filter delivery horizons on the Gantt chart and Kanban lanes
4. How to inspect verifiable test evidence in the detail drawer
And the tour can be stepped through, skipped, or restarted at any time with persistent state in localStorage.
```
```gherkin
Scenario: Persona-Filtered BDD Acceptance Scenario Exploration
Given the stakeholder navigates to the "Personas & Stories" tab
When the stakeholder clicks on persona "Taylor (The Product Manager)"
Then the view filters down exclusively to the user stories authored for Taylor
And selecting a story opens an accordion displaying its exact Gherkin scenarios:
"Given ... When ... Then ..."
And each scenario displays a green verification badge indicating passing blackbox test coverage.
```
```gherkin
Scenario: Executable UAT Sign-Off Verification Matrix and Receipt Export
Given all acceptance criteria for a release feature have passed blackbox verification
When Sasha or Taylor reviews the feature in the visualizer and clicks "Export UAT Verification Receipt"
Then the visualizer generates a cryptographically hashed, timestamped compliance summary:
- Feature ID and governing PRD
- Executable Gherkin scenarios verified
- Git commit SHAs and verified public frontdoor test run timestamps
- Dual sign-off signature block for Product and Security
And the receipt downloads as a tamper-evident PDF or Markdown artifact for SOC2/ISO compliance audit archives.
```

## Rationale & Compelling Value
Transforms technical testing (`pytest-bdd`) into business-visible customer value. Stakeholders can see exact English acceptance criteria verified green against real code commits, establishing unconditional trust across the entire organization.

---
