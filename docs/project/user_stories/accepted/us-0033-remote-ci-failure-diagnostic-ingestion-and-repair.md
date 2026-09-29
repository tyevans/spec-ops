---
id: '0033'
title: Remote CI Failure Diagnostic Ingestion and In-Worktree Repair Loop
status: Accepted
created: 2026-09-29
persona: Morgan (The Autonomous Coding Agent)
feature: FEAT-CIR-01
governing_prd: PRD-0001
---

# US-0033 — Remote CI Failure Diagnostic Ingestion and In-Worktree Repair Loop

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** autonomous coding agent,  
**I want** SpecOps to ingest failed remote CI job logs and inject them directly into my worktree feedback context,  
**So that** I can diagnose and repair platform-specific, matrix, or CI-only failures immediately without waiting for human intervention or navigating external web consoles.

## Acceptance Criteria

```gherkin
Scenario: Ingesting Failed GitHub Actions Log for Autonomous CI Repair
Given an open pull request for branch "task/TASK-0020" created by Morgan
When remote GitHub Actions checks fail on the pull request
And the agent executes "spec-ops worker ci-heal --task TASK-0020"
Then SpecOps executes "gh run view --log-failed" to extract the failed step logs
And extracts the relevant failure trace into ".task-prompt.md"
And opens the existing worktree ".worktrees/task-0020"
And invokes Morgan with the failure context to apply a targeted fix
When Morgan fixes the failure and local preflight passes
Then the worker pushes the updated branch to GitHub and re-triggers remote CI.
```

## Rationale & Compelling Value
Bridges the GitHub CLI directly into the worktree feedback loop as governed by ADR-0004, making Morgan self-sufficient across both local and remote testing boundaries.
