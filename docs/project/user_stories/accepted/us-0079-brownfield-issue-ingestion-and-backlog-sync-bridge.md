---
id: '0079'
title: Brownfield Issue Ingestion and External Backlog Synchronization Bridge
status: Accepted
created: 2026-09-29
persona: Taylor (The Product Manager & Technical Writer)
feature: FEAT-BACK-07
governing_prd: PRD-0005
---

# US-0079 — Brownfield Issue Ingestion and External Backlog Synchronization Bridge

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As a** product manager,
  - **I want** to execute `spec-ops backlog import` to ingest issues from GitHub Issues, Jira, or Linear and `spec-ops backlog export` to generate executive summaries,
  - **So that** our team can adopt SpecOps JIT backlogs without abandoning legacy tracking tools or suffering double-entry administrative toil.

## Acceptance Criteria

```gherkin
Scenario: Ingesting GitHub Issues into Validated Proposed Task Files
Given a GitHub repository with open issues labeled "backlog"
When the product manager runs "spec-ops backlog import --source github --repo org/repo --label backlog"
Then SpecOps converts each open issue into a Markdown task file in "docs/project/backlog/proposed/"
And synthesizes frontmatter containing sequential ID, title, target bounded context, and imported issue URL
And appends the new tasks to "PRIORITY.md" without altering existing completed or refined entries.
```
```gherkin
Scenario: Ingesting Structured CSV/JSON Export from Jira or Linear
Given an issue export file "tickets.json" containing issue key, summary, description, and dependency links
When the product manager runs "spec-ops backlog import --file tickets.json"
Then SpecOps parses issue dependencies, mapping external keys to SpecOps canonical task IDs
And runs the Definition of Ready validator on all imported tasks, flagging incomplete specifications
And outputs an ingestion summary: "Imported 12 tasks (8 ready for refinement, 4 requiring DoR completion)".
```
```gherkin
Scenario: Bi-directional Export of Backlog Status for Executive Roadmaps
Given a refined backlog with milestone assignments and completion timestamps
When the product manager executes "spec-ops backlog export --format markdown --out docs/reference/backlog-snapshot.md"
Then SpecOps generates a structured Diataxis reference document displaying completion burn-up, buffer health, and milestone delivery estimates
Ready for inclusion in executive stakeholder reviews.
-
```

## Rationale & Compelling Value
- **Adoption**: Eliminates the single largest barrier to PMaC adoption—vendor lock-in to external issue trackers.
  - **Regular Usage**: Supports hybrid teams running dual workflows or reporting up to non-technical stakeholders.
  - **Compelling Value**: Turns unstructured web tickets into machine-readable, version-locked Markdown specifications in seconds.

---
