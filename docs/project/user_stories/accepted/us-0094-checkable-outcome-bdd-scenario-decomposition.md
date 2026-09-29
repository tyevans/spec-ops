---
id: '0094'
title: Checkable Outcome-to-BDD Scenario Decomposition and Falsifiability Verification
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-PRD-01
governing_prd: PRD-0003
---

# US-0094 — Checkable Outcome-to-BDD Scenario Decomposition and Falsifiability Verification

## Governing PRD
- [`PRD-0003: Product Discovery, Web PRD Studio & Living UAT Verification`](../../product/accepted/prd-0003-product-discovery-web-prd-studio-and-living-uat-verification.md)

## User Story

**As an** engineering lead,  
  - **I want** `spec-ops prd decompose` to parse each discrete entry under `## Checkable Outcomes` in an accepted PRD and synthesize discrete vertical BDD user stories with executable Gherkin scenario skeletons,  
  - **So that** high-level product requirements translate directly into falsifiable, frontdoor acceptance tests rather than vague monolithic tickets or generic placeholder user stories.

## Acceptance Criteria

```gherkin
Scenario: Decomposing a PRD by its checkable outcomes into discrete BDD user stories
Given an accepted PRD "PRD-0002" with 3 distinct checkable outcomes in "docs/project/product/accepted/prd-0002-telemetry.md":
| Outcome 1: CLI emits JSON metrics matching telemetry schema when run with --json |
| Outcome 2: Heartbeat agent transmits ping payload to visualizer every 5 seconds   |
| Outcome 3: Disconnected agents trigger stale warning alert within 15 seconds      |
When Jordan runs "spec-ops prd decompose PRD-0002 --by-outcomes"
Then SpecOps parses the 3 checkable outcomes
And generates 3 distinct BDD user story files under "docs/project/user_stories/accepted/"
And each user story frontmatter sets "governing_prd: PRD-0002" and maps the specific outcome ID
And each user story contains an executable Gherkin skeleton reflecting the outcome behavior.
```
```gherkin
Scenario: Rejecting non-falsifiable or subjective outcomes during decomposition
Given an accepted PRD "PRD-0003" containing a subjective outcome "The system should feel noticeably faster"
When Jordan runs "spec-ops prd decompose PRD-0003 --by-outcomes"
Then the command exits with exit code 1
And outputs a falsifiability failure: "Outcome 'The system should feel noticeably faster' is non-falsifiable; refine into an observable metric or contract"
And no user stories or backlog tasks are generated until the outcome is corrected.
```
```gherkin
Scenario: Linking synthesized user stories back into the PRD and task frontmatter
Given the successful outcome-driven decomposition of "PRD-0002" into stories "US-0059", "US-0060", and "US-0061"
When Jordan inspects "docs/project/product/accepted/prd-0002-telemetry.md"
Then the "## Linked User Stories" section contains references to "US-0059", "US-0060", and "US-0061"
And the generated vertical slice tasks in "docs/project/backlog/proposed/" cite their governing stories in "governing_stories".
-
```

## Rationale & Compelling Value
- *Adoption*: Bridges the communication gap between product discovery and engineering delivery. Non-technical PMs write checkable outcomes in Markdown, and SpecOps automatically translates them into engineering-ready BDD specs.
  - *Regular Usage*: Invoked every time a shaped PRD is accepted and handed off for engineering execution.
  - *Compelling Value*: Directly addresses current `PRDDecomposer` limitations (which emits 1 generic placeholder story) by ensuring a 1:1 contractual mapping between customer requirements and executable Gherkin tests.

---
