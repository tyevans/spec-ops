---
id: '0090'
title: Preserved Worktree AI-to-Human Handover Brief and Debug Cheatsheet
status: Accepted
created: 2026-09-29
persona: Riley (The Human IC Developer)
feature: FEAT-RESC-04
governing_prd: PRD-0004
---

# US-0090 — Preserved Worktree AI-to-Human Handover Brief and Debug Cheatsheet

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As a** human software engineer taking over a failed autonomous task,
  - **I want** SpecOps to automatically generate a `HANDOVER.md` file inside the preserved worktree and output a terminal quick-start cheatsheet,
  - **So that** I have immediate copy-paste commands to enter the workspace, reproduce the exact failing step, and inspect governing ADR rules without cognitive friction.

## Acceptance Criteria

```gherkin
Scenario: Automatic generation of HANDOVER.md upon agent exhaustion
Given an autonomous worker exhausts max attempts on "TASK-0014"
When the worker engine halts and preserves the worktree at ".worktrees/task-0014"
Then a structured handover document ".worktrees/task-0014/HANDOVER.md" is generated containing:
| Section               | Content                                                              |
| Task Header           | Canonical ID, title, and target bounded context                      |
| Attempt Timeline      | Chronological summary of attempts 1, 2, and 3 with exit codes        |
| Exact Failure Log     | Isolated error traceback from the last preflight run                 |
| Governing Context     | Hyperlinks to governing PRD, governing user story, and baseline ADRs |
| Reproduction Command  | Exact CLI command to reproduce the failure (e.g. `uv run pytest ...`)|
| Completion Command    | Command to finalize rescue: `spec-ops rescue TASK-0014 --complete`   |
```
```gherkin
Scenario: Terminal cheatsheet display upon running rescue inspection
Given an engineer runs "spec-ops rescue TASK-0014"
When the worktree metadata is displayed
Then the terminal renders a copy-paste developer cheatsheet:
"""
🚀 Rescue Quickstart:
1. Jump into worktree:  cd .worktrees/task-0014
2. Reproduce failure:   uv run pytest tests/test_curator.py -k test_buffer_sync
3. Inspect changes:     git diff HEAD
4. Complete & merge:    spec-ops rescue TASK-0014 --complete
5. Discard & reset:     spec-ops rescue reset TASK-0014
"""
```
```gherkin
Scenario: Ensuring HANDOVER.md is excluded from production commits
Given the engineer has resolved the bug inside ".worktrees/task-0014"
When the engineer executes "spec-ops rescue TASK-0014 --complete"
Then "HANDOVER.md" and ".task-prompt.md" are automatically purged prior to git staging
And zero ephemeral handover artifacts are committed to "main".
-
```

## Rationale & Compelling Value
- **Adoption**: Eliminates context-switching overhead. Developers can start fixing code within 10 seconds of receiving a failure notification.
  - **Regular Usage**: Serves as the standard ergonomic handover protocol between AI agents and human teammates on every failed task.
  - **Compelling Value**: Bridges the agent-to-human collaboration gap with zero noise, ensuring ephemeral triage files never pollute git history.

---
