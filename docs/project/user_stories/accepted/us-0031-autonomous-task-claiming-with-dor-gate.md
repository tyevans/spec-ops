---
id: '0031'
title: Autonomous Task Claiming with Dependency and Definition of Ready Gate
status: Accepted
created: 2026-09-29
persona: Morgan (The Autonomous Coding Agent)
feature: FEAT-CLM-01
governing_prd: PRD-0004
---

# US-0031 — Autonomous Task Claiming with Dependency and Definition of Ready Gate

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As an** autonomous coding agent,  
**I want** to execute `spec-ops worker claim --auto` to atomically claim the highest-priority unblocked task that satisfies the Definition of Ready (DoR),  
**So that** I never waste execution cycles working on tasks with unmet dependencies, missing PRD links, or absent acceptance criteria.

## Acceptance Criteria

```gherkin
Scenario: Successfully Claiming Highest-Priority Ready Task
Given a task "TASK-0016" at the top of "docs/project/backlog/PRIORITY.md" in status "Refined"
And all dependencies of "TASK-0016" are in "docs/project/backlog/complete/"
And "TASK-0016" frontmatter links to an accepted PRD, governing ADRs, and Gherkin scenarios
When the agent runs "spec-ops worker claim --auto"
Then the worker engine selects "TASK-0016"
And verifies that all DoR criteria are satisfied
And provisions worktree ".worktrees/task-0016" on branch "task/TASK-0016"
And returns exit code 0 with the claimed task metadata.
```

```gherkin
Scenario: Blocking Claim on Incomplete Task Dependencies
Given a task "TASK-0017" at the top of "PRIORITY.md" that depends on "TASK-0016"
And "TASK-0016" is not yet in "docs/project/backlog/complete/"
When the agent runs "spec-ops worker claim --auto"
Then the worker engine skips "TASK-0017" due to unsatisfied dependency
And evaluates the next sequential unblocked task in "PRIORITY.md"
And reports dependency blocking status in stderr.
```

## Rationale & Compelling Value
An autonomous claiming command with built-in DoR validation ensures Morgan only begins work that is mathematically ready to be implemented.
