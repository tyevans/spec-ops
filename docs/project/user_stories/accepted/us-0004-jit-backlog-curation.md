---
id: '0004'
title: Just-In-Time Backlog Curation and Buffer Replenishment
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-JIT-01
governing_prd: PRD-0001
---

# US-0004 — Just-In-Time Backlog Curation and Buffer Replenishment

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** engineering lead,  
**I want** to run `spec-ops curate` automatically or on demand,  
**So that** unblocked tasks in `proposed/` are promoted to `refined/` just-in-time to maintain a lean buffer of ~10 ready tasks without specification drift.

## Acceptance Criteria

### Scenario 1: Replenishing an Under-Buffered Backlog
```gherkin
Given a backlog where refined tasks have fallen below the warning threshold (<3 tasks)
And unblocked tasks exist in "docs/project/backlog/proposed/"
When the lead runs "spec-ops curate"
Then eligible tasks are promoted to "docs/project/backlog/refined/"
And the refined buffer count moves toward the target buffer of 10
And "PRIORITY.md" is atomically updated to reflect the new task locations.
```
