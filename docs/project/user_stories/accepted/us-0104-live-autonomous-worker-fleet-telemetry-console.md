---
id: '0104'
title: Live Autonomous Worker Fleet Telemetry and Worktree Operations Console
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-VIS-04
governing_prd: PRD-0005
---

# US-0104 — Live Autonomous Worker Fleet Telemetry and Worktree Operations Console

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** engineering lead,
  - **I want** a dedicated 'Lead Operations Console' tab in the visualizer displaying real-time agent fleet telemetry and worktree health,
  - **So that** I can monitor parallel agent executions across isolated git worktrees, track self-healing retry cycles, detect deadlocked workers, and trigger one-click human takeover commands before CI pipelines fail.

## Acceptance Criteria

```gherkin
Scenario: Live Active Worktree Fleet Telemetry Display
Given 3 autonomous coding agents are executing tasks in concurrent git worktrees:
| Worktree Directory    | Task ID   | Task Title                         | Branch          | Status       | Retries | Current Preflight Hook |
| .worktrees/task-0012  | TASK-0012 | Implement profile parser           | feat/task-0012  | Running      | 0/3     | uv run pytest          |
| .worktrees/task-0015  | TASK-0015 | AST file decomposition helper      | feat/task-0015  | Self-Healing | 2/3     | spec-ops health        |
| .worktrees/task-0018  | TASK-0018 | Governed spike lifecycle runner    | feat/task-0018  | Running      | 1/3     | git commit preflight   |
When Jordan opens the "Lead Console" tab in the visualizer
Then a real-time fleet grid renders each active worktree with branch name, status badge, and elapsed runtime
And the retry counter displays progress indicators (e.g. "2/3 Self-Healing")
And the telemetry refreshes automatically without requiring manual browser reloads.
```
```gherkin
Scenario: Urgent Visual Alerting on Stalled Worker Exhaustion
Given an autonomous worker in ".worktrees/task-0015" fails its 3rd self-healing attempt and stalls
When the visualizer receives updated fleet state
Then a high-visibility rescue banner appears at the top of the Lead Console
And the row for "TASK-0015" transitions to status "Stalled: Human Takeover Required" with an amber alert border
And the dashboard displays the exact diagnostic failure excerpt and the last generated agent prompt.
```
```gherkin
Scenario: One-Click Rescue Launch and Diagnostic Handshake
Given a stalled worker task displayed in the visualizer Lead Console
When Jordan clicks the "🚀 Launch Rescue Takeover" button on the task card
Then the console copies the exact terminal command "spec-ops rescue TASK-0015" to the system clipboard
And opens an inspection drawer showing the file diff, last preflight terminal output, and instructions for developer handover.
```

## Rationale & Compelling Value
Prevents silent agent failures and runaway compute loops. Leads can spot struggling agents in seconds and perform graceful human takeovers before corrupt work or stale worktrees build up.

---
