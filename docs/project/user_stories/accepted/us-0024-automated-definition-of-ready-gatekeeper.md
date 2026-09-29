---
id: '0024'
title: Automated Definition of Ready Gatekeeper and Ticket Health Audit
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-DOR-01
governing_prd: PRD-0005
---

# US-0024 — Automated Definition of Ready Gatekeeper and Ticket Health Audit

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** engineering lead,  
**I want** `spec-ops curate` and `spec-ops backlog verify-dor` to enforce strict Definition of Ready (DoR) compliance,  
**So that** proposed tasks lacking executable Gherkin acceptance criteria, linked personas, cited ADRs, or bounded contexts are blocked from entering the ready buffer, preventing autonomous workers from hallucinating on ambiguous specifications.

## Acceptance Criteria

```gherkin
Scenario: Promoting Only Fully Compliant Tasks to Refined Buffer
Given an under-buffered ready queue (< 3 tasks)
And proposed task "0024-implement-audit.md" satisfies all 7 DoR rules:
  | Rule Check                     | Status |
  | Complete YAML frontmatter      | Pass   |
  | Linked Persona & PRD           | Pass   |
  | Cited Governing ADRs           | Pass   |
  | Executable Gherkin Scenarios   | Pass   |
  | Defined Target Bounded Context | Pass   |
  | Feasible File Limit Scope      | Pass   |
  | Mutation Testing Scope Defined | Pass   |
When the lead executes "spec-ops curate"
Then "TASK-0024" is promoted to "docs/project/backlog/refined/"
And "PRIORITY.md" is updated atomically.
```

```gherkin
Scenario: Rejecting Half-Baked Proposed Tasks Lacking Gherkin Criteria
Given a proposed task "0025-ambiguous-task.md" containing only bullet points and no "Given ... When ... Then" scenarios
When the lead runs "spec-ops backlog verify-dor"
Then the command exits with code 1
And flags "TASK-0025: DoR Violation - Missing executable Gherkin acceptance criteria (ADR-0006)"
And prevents "spec-ops curate" from promoting TASK-0025 until the criteria are authored.
```

```gherkin
Scenario: Rejecting Tasks Violating Single-Responsibility Scope
Given a proposed task whose specification proposes modifying 8 different bounded contexts spanning >500 expected lines
When the lead runs "spec-ops backlog verify-dor --strict"
Then the task is rejected with advice to decompose into thin vertical slices or architectural spikes (ADR-0002).
```

## Rationale & Compelling Value
Enforces 'Garbage In, Blocked at Gate' quality control. Jordan ensures only high-conviction, executable tasks reach autonomous coding agents, dramatically cutting worktree preflight failures.
