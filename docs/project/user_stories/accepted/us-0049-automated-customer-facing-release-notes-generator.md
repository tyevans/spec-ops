---
id: '0049'
title: Automated Customer-Facing Release Notes and Business Value Changelog Generator
status: Accepted
created: 2026-09-29
persona: Taylor (The Product Manager)
feature: FEAT-REL-01
governing_prd: PRD-0001
---

# US-0049 — Automated Customer-Facing Release Notes and Business Value Changelog Generator

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** product manager,  
**I want** `spec-ops` to generate human-readable, customer-facing release notes from shipped PRD checkable outcomes and passed Gherkin user stories,  
**So that** I can publish feature announcements and release communications instantly upon milestone completion without manually summarizing git commit logs.

## Acceptance Criteria

```gherkin
Scenario: Generating Customer Release Notes for a Completed Milestone
Given a completed milestone "Milestone 1: Foundations" in "ROADMAP.md" with linked PRDs and stories
When Taylor executes "spec-ops release notes --milestone M1 --format markdown"
Then a release notes document is generated at "docs/reference/release-notes-m1.md"
And the content categorizes changes by customer-visible outcome:
  | Section              | Content Source                                    |
  | New Capabilities     | Shipped PRD "What good looks like" sections       |
  | User Scenarios Added | Passed Gherkin user story summaries               |
  | Persona Impacts      | Persona benefits from "PERSONAS.md"               |
And internal developer refactors and invisible spike commits are excluded.
```

```gherkin
Scenario: Exporting Clean HTML for Stakeholder Newsletters
Given generated release notes for an accepted release
When Taylor runs "spec-ops release notes --milestone M1 --format html --branded"
Then a styled, standalone HTML email template is created
And links each new capability directly to the live GitHub Pages documentation and visualizer permalink.
```

## Rationale & Compelling Value
Directly surfaces business value. Connects shipped code back to user personas, demonstrating tangible progress to external customers and internal leadership.
