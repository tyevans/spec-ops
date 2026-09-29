---
id: '0071'
title: Bounded-Context Diataxis Documentation Scaffolding and Living Spec Linking
status: Accepted
created: 2026-09-29
persona: Taylor (The Product Manager & Technical Writer)
feature: FEAT-SCAF-06
governing_prd: PRD-0005
---

# US-0071 — Bounded-Context Diataxis Documentation Scaffolding and Living Spec Linking

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As a** product manager and domain collaborator,  
**I want** `spec-ops` to scaffold modular Diataxis documentation quadrants for new domain bounded contexts with automatic cross-linking to PRDs, user stories, and interactive visualizer views,  
**So that** non-technical stakeholders and developers can explore feature tutorials, operational recipes, API references, and domain explanations specific to each sub-domain as the project expands.

## Acceptance Criteria

```gherkin
Scenario: Scaffolding Diataxis quadrant for a new bounded context
Given a project with an established "billing" bounded context configured in "specops.toml"
When the product manager runs "spec-ops scaffold diataxis --bc billing --title 'Billing & Subscription Engine'"
Then quadrant directories "docs/how-to/billing/", "docs/reference/billing/", and "docs/explanation/billing/" are created
And starter markdown templates are installed with metadata linking to governing PRDs and user stories
And the main documentation index "docs/index.md" is updated with a section for the new bounded context.
```
```gherkin
Scenario: Embedding deep links to the living 2D visualizer
Given a newly scaffolded bounded context explanation document "docs/explanation/billing/architecture.md"
When the builder compiles documentation with "spec-ops docs build"
Then the rendered HTML page includes an embedded interactive link to the visualizer pre-filtered to the "billing" component ("visualizer/?focus=billing")
And verifies that all internal cross-links to user stories in "docs/project/user_stories/" resolve cleanly.
```
```gherkin
Scenario: Preventing duplicate bounded context scaffolding
Given an existing documentation quadrant in "docs/reference/billing/"
When the user runs "spec-ops scaffold diataxis --bc billing" without "--overwrite"
Then the command warns that Diataxis documentation for "billing" already exists
And exits cleanly without overwriting existing files.
```

## Rationale & Compelling Value
Eliminates "documentation sprawl" and broken links by tightly binding Diataxis documentation quadrants directly to domain bounded contexts and interactive visualizer subgraphs.

---
