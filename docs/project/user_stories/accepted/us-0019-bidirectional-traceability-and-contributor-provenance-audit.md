---
id: '0019'
title: Bidirectional End-to-End Traceability and Contributor Provenance Audit
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-AUD-01
governing_prd: PRD-0005
---

# US-0019 — Bidirectional End-to-End Traceability and Contributor Provenance Audit

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** engineering lead overseeing hybrid human-agent delivery,  
**I want** to execute `spec-ops audit traceability` and view an interactive Traceability Matrix in the visualizer,  
**So that** I can verify an unbroken bidirectional lineage from customer personas down to merged commits and PRs, detect unanchored rogue commits, and attribute delivery velocity between autonomous agents and human developers.

## Acceptance Criteria

```gherkin
Scenario: Verifying Unbroken Traceability from Persona to Merged Commits
Given a project repository with accepted Personas, PRDs, User Stories, and Backlog Tasks
And git history containing merged commits with structured trailers referencing task IDs
When the lead runs "spec-ops audit traceability"
Then the command exits with code 0
And outputs a verified traceability matrix linking each Persona to its PRDs, Stories, Tasks, and Git Commits
And reports "Traceability Integrity: 100% (0 unanchored commits, 0 orphaned stories)".
```

```gherkin
Scenario: Flagging Unanchored Commits and Orphaned Tasks
Given a git commit merged to "main" without a "Task-ID" or "SpecOps-Task" trailer
And a completed task in "docs/project/backlog/complete/" with no linked git commits
When the lead runs "spec-ops audit traceability"
Then the command exits with code 1
And reports a warning identifying the unanchored commit hash and author
And highlights the orphaned task as missing delivery provenance.
```

```gherkin
Scenario: Contributor Provenance Attribution
Given a repository with commits authored by autonomous workers containing "Provenance: spec-ops autonomous worker"
And commits authored by human developers
When the lead runs "spec-ops audit traceability --contributions"
Then the output breaks down delivered tasks by contributor type:
  | Contributor Class   | Tasks Delivered | Merged Commits | Verification Pass Rate |
  | Autonomous Agents   | 14              | 28             | 93.3%                  |
  | Human Developers    | 9               | 15             | 100.0%                 |
And updates the visualizer Traceability view with contributor filter chips.
```

## Rationale & Compelling Value
Eliminates 'ghost work' and unreviewed agent PR merges. Jordan can instantly answer 'which PRs delivered value for which customer persona?' during executive syncs and sprint reviews.
