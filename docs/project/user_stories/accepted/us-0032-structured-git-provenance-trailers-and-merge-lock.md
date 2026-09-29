---
id: '0032'
title: Structured Git Provenance Trailers and Atomic Integration under Merge Lock
status: Accepted
created: 2026-09-29
persona: Morgan (The Autonomous Coding Agent)
feature: FEAT-VCS-01
governing_prd: PRD-0001
---

# US-0032 — Structured Git Provenance Trailers and Atomic Integration under Merge Lock

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** autonomous coding agent,  
**I want** SpecOps to automatically construct structured git commit messages with provenance trailers and coordinate squash-merge integration into `main` under `MERGE_LOCK`,  
**So that** every autonomous change has complete audit traceability to governing specs and tasks without risking git race conditions during concurrent execution.

## Acceptance Criteria

```gherkin
Scenario: Creating Standardized Git Commit with Provenance Trailers
Given an agent worktree with verified changes for "TASK-0018"
And "TASK-0018" specifies governing ADRs "ADR-0003, ADR-0005" and title "Support JSON output"
When the worker engine finalizes the task
Then a git commit is generated with a conventional subject "feat(task-0018): Support JSON output"
And the commit body includes structured git trailers:
  | Trailer Key    | Trailer Value                   |
  | Task-ID        | TASK-0018                       |
  | Governing-ADRs | ADR-0003, ADR-0005              |
  | Provenance     | spec-ops autonomous worker      |
And the commit is squash-merged into "main" under MERGE_LOCK
And the task file is atomically moved to "docs/project/backlog/complete/" on "main".
```

## Rationale & Compelling Value
Traceability between running code, commits, and architectural decisions is essential for compliance and team trust in AI-generated software.
