---
id: '0021'
title: Autonomous Backlog Bottleneck and Critical Path Deadlock Detection
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-BNK-01
governing_prd: PRD-0005
---

# US-0021 — Autonomous Backlog Bottleneck and Critical Path Deadlock Detection

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** engineering lead,  
**I want** to execute `spec-ops backlog bottlenecks` and inspect the Bottleneck Radar in the visualizer,  
**So that** I can automatically detect dependency deadlocks, circular blocking chains, and high-fanout choke-point tasks delaying critical delivery paths before agent workers starve.

## Acceptance Criteria

```gherkin
Scenario: Identifying High-Fanout Dependency Choke Points
Given a backlog where multiple proposed tasks in different bounded contexts depend on a single unrefined task "TASK-0013"
When the lead runs "spec-ops backlog bottlenecks"
Then the command outputs a prioritized bottleneck analysis:
  | Choke Task | Downstream Blocked Tasks | Critical Path Delay | Recommended Action    |
  | TASK-0013  | 6 tasks                  | 3 delivery horizons | Prioritize Refinement |
And highlights TASK-0013 as a primary choke point in the visualizer graph with a pulsing alert aura.
```

```gherkin
Scenario: Detecting Circular Dependency Deadlocks
Given task "TASK-0021" lists "TASK-0022" in its dependencies
And task "TASK-0022" directly or transitively depends on "TASK-0021"
When the lead runs "spec-ops backlog bottlenecks"
Then the command exits with code 1
And displays the exact circular cycle: "TASK-0021 -> TASK-0022 -> TASK-0021"
And provides actionable CLI suggestions to break the dependency cycle.
```

```gherkin
Scenario: Pre-empting Ready Buffer Starvation
Given a refined queue containing only 1 unassigned task
And all remaining proposed tasks are blocked by pending in-flight tasks
When the lead executes "spec-ops backlog bottlenecks --forecast"
Then the command warns: "Buffer Starvation Imminent: Ready queue will deplete in 1 cycle with zero unblocked candidates"
And suggests which in-flight tasks require immediate unblocking or rescue to replenish the ready buffer.
```

## Rationale & Compelling Value
Replaces tedious manual dependency tracing with automated critical-path analysis. Jordan immediately spots blocking tasks that unlock downstream multi-agent parallelism.
