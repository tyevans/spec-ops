---
id: '0035'
title: Stalled Autonomous Worktree Inspection and Diagnostic Takeover
status: Accepted
created: 2026-09-29
persona: Riley (The Human IC Developer)
feature: FEAT-RSC-01
governing_prd: PRD-0001
---

# US-0035 — Stalled Autonomous Worktree Inspection and Diagnostic Takeover

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** human software engineer working alongside autonomous coding agents,  
**I want** to run `spec-ops rescue <task-id>` to inspect preserved worktrees and review failure diagnostics when an agent stalls,  
**So that** I can seamlessly take over the workspace, patch the failing code, and complete integration into `main` without re-running failing steps from scratch or losing in-progress work.

## Acceptance Criteria

```gherkin
Scenario: Inspecting a stalled agent worktree with diagnostics
Given an autonomous worker session has exhausted its self-healing attempts on task "TASK-0011"
And the isolated worktree ".worktrees/task-0011" is preserved with preflight diagnostics in ".task-prompt.md"
When the engineer executes "spec-ops rescue TASK-0011"
Then the CLI displays the worktree directory path, git branch, and dirty status
And the last preflight error diagnostics from ".task-prompt.md" are rendered to the terminal
And instructions are provided for completing or discarding the rescue.
```

```gherkin
Scenario: Human takeover, verification, and atomic merge into main
Given an engineer has corrected the source files inside ".worktrees/task-0011"
When the engineer executes "spec-ops rescue TASK-0011 --complete"
Then preflight verification executes inside the worktree
And upon preflight passing, any uncommitted changes are committed with trailer "SpecOps-Task: TASK-0011"
And the feature branch is squash-merged into "main" under MERGE_LOCK
And task "TASK-0011" is moved from "docs/project/backlog/refined/" to "docs/project/backlog/complete/"
And the isolated worktree directory and branch are cleanly removed.
```

```gherkin
Scenario: Discarding an irreparably broken agent worktree
Given a stalled worktree ".worktrees/task-0099" that is deemed unrecoverable
When the engineer executes "spec-ops rescue TASK-0099 --discard"
Then the worktree directory ".worktrees/task-0099" is deleted
And its associated git branch is deleted
And task "TASK-0099" remains safely in "docs/project/backlog/refined/" for re-assignment.
```

## Rationale & Compelling Value
Transforms the dreaded 'AI broke my repo' experience into a smooth handover. Complete elimination of worktree lockout and zero wasted compute.
