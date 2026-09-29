---
id: '0028'
title: In-Worktree Pre-Flight Verification and Iterative Self-Healing Feedback Loop
status: Accepted
created: 2026-09-29
persona: Morgan (The Autonomous Coding Agent)
feature: FEAT-HLN-01
governing_prd: PRD-0004
---

# US-0028 — In-Worktree Pre-Flight Verification and Iterative Self-Healing Feedback Loop

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As an** autonomous coding agent,  
**I want** local preflight checks to run automatically inside my worktree and provide structured diagnostic feedback upon failure,  
**So that** I can autonomously diagnose, self-heal, and verify code modifications across multiple repair attempts before any branch commit or PR dispatch.

## Acceptance Criteria

```gherkin
Scenario: Autonomous Self-Healing on Preflight Health Check Violation
Given an isolated worktree executing task "TASK-0014"
When the agent implements code where a source file contains 520 lines
And the worker engine executes the preflight suite "uv run spec-ops health"
Then the preflight check fails reporting a file length violation on line 520
And the worker engine appends the exact error log and file location to the agent feedback prompt
And re-invokes the agent in the worktree for repair attempt 2
When the agent decomposes the module into two files under 400 lines each
And preflight re-runs cleanly
Then the worker marks preflight as passed and proceeds to staging.
```

```gherkin
Scenario: Graceful Worktree Preservation on Exhausted Self-Healing Retries
Given an isolated worktree executing task "TASK-0014"
When the agent fails preflight verification across all configured maximum attempts (3 attempts)
Then the worker halts without creating a broken git commit
And preserves the worktree at ".worktrees/task-0014" with diagnostic failure logs
And outputs a human takeover command "spec-ops rescue TASK-0014".
```

## Rationale & Compelling Value
A localized in-worktree self-healing loop turns catastrophic failures into iterative, deterministic repair cycles, allowing Morgan to resolve 90%+ of issues autonomously.
