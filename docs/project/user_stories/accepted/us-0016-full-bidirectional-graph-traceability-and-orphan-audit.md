---
id: '0016'
title: Full Bidirectional Graph Traceability and Orphan Work Item Audit
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-TRC-01
governing_prd: PRD-0001
---

# US-0016 — Full Bidirectional Graph Traceability and Orphan Work Item Audit

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** agentic systems architect,  
**I want** to run `spec-ops trace --verify` to audit end-to-end bidirectional graph linkages between Personas, PRDs, User Stories, Backlog Tasks, and ADRs,  
**So that** orphaned work items, unanchored tasks, broken frontmatter references, and circular dependency chains are caught before JIT backlog curation.

## Acceptance Criteria

```gherkin
Scenario: Clean repository passing bidirectional graph verification
Given a repository where all tasks cite accepted stories, all stories cite accepted PRDs, and all PRDs cite valid personas
When the architect runs "spec-ops trace --verify"
Then the command exits with code 0
And reports "Traceability Invariant Met: 100% graph connectivity with 0 orphan entities".
```

```gherkin
Scenario: Detecting an orphaned task with a non-existent story link
Given a task file in "docs/project/backlog/proposed/0030-orphan-feature.md" citing "story: US-9999"
And "US-9999" does not exist in "docs/project/user_stories/"
When the architect runs "spec-ops trace --verify"
Then the command exits with code 1
And reports "Graph Error: Task 0030-orphan-feature references missing story 'US-9999'".
```

```gherkin
Scenario: Detecting cyclical task dependencies in the backlog graph
Given task "TASK-0010" has "dependencies: [TASK-0011]"
And task "TASK-0011" has "dependencies: [TASK-0010]"
When the architect runs "spec-ops trace --verify"
Then the command exits with code 1
And reports "Cyclic Backlog Dependency Detected: TASK-0010 <-> TASK-0011"
And outputs the cycle path.
```

## Rationale & Compelling Value
Enforces strict relational DAG integrity: every unit of engineering work is bi-directionally validated against a persona need and an ADR before it can be refined or scheduled.
