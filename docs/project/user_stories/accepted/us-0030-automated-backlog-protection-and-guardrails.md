---
id: '0030'
title: Automated Backlog Protection and Accidental Modification Guardrails
status: Accepted
created: 2026-09-29
persona: Morgan (The Autonomous Coding Agent)
feature: FEAT-PRO-01
governing_prd: PRD-0001
---

# US-0030 — Automated Backlog Protection and Accidental Modification Guardrails

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** autonomous coding agent,  
**I want** SpecOps to automatically detect and revert accidental modifications to shared project management files within my feature worktree,  
**So that** my commits strictly contain functional code and tests, preventing git merge conflicts and branch rejections during parallel multi-agent development.

## Acceptance Criteria

```gherkin
Scenario: Intercepting and Reverting Accidental Backlog Changes
Given an isolated worktree on branch "task/TASK-0015"
When the agent implements feature code in "src/spec_ops/backlog/"
And the agent inadvertently modifies "docs/project/backlog/PRIORITY.md" and "docs/project/backlog/refined/task-0015.md"
When the worker engine initiates commit preparation
Then the worker detects modifications inside "docs/project/backlog/"
And automatically executes a git checkout HEAD on "docs/project/backlog/" to discard the changes
And stages only legitimate source code and test files in "src/" and "tests/"
And creates a commit containing zero modifications to shared backlog indices.
```

## Rationale & Compelling Value
Silently enforces ADR-0005 backlog isolation. Morgan is freed from manual git branch hygiene, ensuring 100% clean squash merges into `main`.
