---
id: '0084'
title: Conventional Commit Slice Classification and Standardized Git Trailer Lineage
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-WORK-05
governing_prd: PRD-0004
---

# US-0084 — Conventional Commit Slice Classification and Standardized Git Trailer Lineage

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As a** human software engineer reviewing repository history,
  - **I want** autonomous workers to classify commit messages using conventional commit types based on vertical slice metadata and embed standardized git trailers,
  - **So that** the commit log clearly communicates intent, integrates seamlessly with automated changelog tools, and maintains bidirectional auditability to governing ADRs and PRDs.

## Acceptance Criteria

```gherkin
Scenario: Deriving Conventional Commit Type from Task Slice Metadata
Given a refined task "TASK-0018" with slice type "spike" and title "Evaluate mutmut mutation testing"
And governing ADRs "ADR-0007, ADR-0009" and governing PRD "PRD-0001"
When the worker engine creates the final squash commit
Then the commit subject line is formatted as "spike(task-0018): Evaluate mutmut mutation testing"
And the commit body contains standard RFC-822 git trailers:
| Trailer Key    | Trailer Value                                      |
| SpecOps-Task   | TASK-0018                                          |
| SpecOps-Slice  | spike                                              |
| SpecOps-PRD    | PRD-0001                                           |
| SpecOps-ADR    | ADR-0007, ADR-0009                                 |
| Provenance     | spec-ops-worker (autonomous)                       |
And "git log -1 --pretty=full" outputs the structured trailers cleanly.
```
```gherkin
Scenario: Bug Fix and Refactoring Slice Commit Formatting
Given a task "TASK-0021" with slice type "refactor" and title "Decompose worker module into submodules"
When the worker finalizes and squash-merges the task
Then the commit subject is formatted as "refactor(task-0021): Decompose worker module into submodules"
And the trailers verify that "SpecOps-Slice: refactor" is recorded.
-
```

## Rationale & Compelling Value
- *Adoption*: Integrates directly into enterprise semantic-release tooling, commit linters, and pull request inspection pipelines.
  - *Regular Usage*: Human engineers inspecting `git log` or `git blame` gain immediate context on why a change occurred, which ADR governed it, and what task prompted it without leaving their terminal.
  - *Compelling Value*: Provides ironclad, audit-ready provenance connecting commits to architectural decisions, drastically reducing human PR review fatigue.

---
