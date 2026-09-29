---
id: '0026'
title: Living Visualizer Lead Console with Real-Time Agent Fleet Telemetry
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-OPS-01
governing_prd: PRD-0005
---

# US-0026 — Living Visualizer Lead Console with Real-Time Agent Fleet Telemetry

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** engineering lead,  
**I want** a dedicated 'Lead Operations Console' tab in the SpecOps visualizer,  
**So that** I can observe real-time agent fleet telemetry (active worktrees, self-healing retries, in-worktree preflight statuses, ready buffer levels, and stalled tasks awaiting rescue) in a single unified command deck.

## Acceptance Criteria

```gherkin
Scenario: Live Agent Fleet and Worktree Telemetry
Given multiple autonomous workers running across isolated git worktrees
When the lead navigates to the "Lead Console" tab in the visualizer
Then an active fleet status grid displays:
  | Task ID   | Worktree Path             | Branch          | Status       | Attempt | Active Preflight Check |
  | TASK-0013 | .worktrees/task-0013      | feat/task-0013  | Executing    | 1/3     | uv run pytest          |
  | TASK-0014 | .worktrees/task-0014      | feat/task-0014  | Self-Healing | 2/3     | Fixing file limit      |
And the telemetry updates dynamically without page reloads.
```

```gherkin
Scenario: Real-Time Alerts for Stalled Tasks Requiring Human Rescue
Given an autonomous worker has exhausted its maximum attempts (3/3) and stalled
When the lead views the Lead Console
Then an urgent rescue banner appears highlighting "TASK-0014 Stalled: Awaiting Human Takeover"
And clicking "Inspect Worktree" displays the agent's failure log and ".task-prompt.md" feedback.
```

```gherkin
Scenario: One-Click Rescue Launch
Given a stalled task displayed in the rescue panel of the Lead Console
When the lead clicks "Takeover Task"
Then the console copies the exact command "spec-ops rescue inspect TASK-0014" to the clipboard
And provides a deep link directly to the task specification and failure diff.
```

## Rationale & Compelling Value
Single-pane-of-glass operational visibility. Jordan gains real-time control and situational awareness over the entire autonomous workforce without ever hunting through background terminal logs.
