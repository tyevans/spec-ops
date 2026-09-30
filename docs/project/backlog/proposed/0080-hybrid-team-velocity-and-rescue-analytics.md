---
id: '0080'
title: Hybrid Team Delivery Velocity and Autonomous Agent Rescue Analytics
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0067
  - TASK-0070
governing_adrs:
  - ADR-0001
  - ADR-0003
  - ADR-0005
  - ADR-0007
governing_prds:
  - PRD-0005
governing_stories:
  - US-0022
target_bc: backlog
---

# TASK-0080: Hybrid Team Delivery Velocity and Autonomous Agent Rescue Analytics

## Summary
Implement hybrid engineering team velocity and autonomous worker rescue analytics (`spec-ops report velocity [--window 14d] [--json]`). Compute delivery throughput across both human developers and autonomous AI agents, track rescue intervention frequency and failure clustering patterns, analyze mean time to unblock, and export rolling velocity metrics for executive reviews.

## Problem Statement & Context
Hybrid engineering workflows involve both human engineers and autonomous AI agent workers operating concurrently. Traditional agile metrics fail to account for agent-specific dynamics such as prompt retry loops, worktree rescue interventions, and autonomous throughput velocity. Without empirical analytics, engineering leaders cannot pinpoint recurring failure hotspots, determine the true human rescue burden, or forecast delivery schedules accurately. SpecOps requires specialized velocity reporting and rescue telemetry.

## User Stories & Scenarios Satisfied
- **US-0022: Hybrid Team Velocity and Autonomous Agent Rescue Analytics**
  - *Scenario: Generating Hybrid Velocity and Throughput Metrics*
    - Given committed work items completed by both human contributors and autonomous agent workers over the past 30 days
    - When the engineering manager runs "spec-ops report velocity"
    - Then the command outputs throughput metrics broken down by contributor category (Human vs Agent), average cycle time, and task completion velocity.
  - *Scenario: Visualizing Rescue Burden and Failure Clustering*
    - Given task execution logs containing worktree rescue interventions
    - When "spec-ops report velocity --rescues" is executed
    - Then the report identifies recurring failure clusters (e.g. preflight test failures vs lint errors) and computes the ratio of human intervention time to autonomous execution time.
  - *Scenario: Exporting Velocity Trends for Executive Reviews*
    - Given rolling delivery history
    - When "spec-ops report velocity --export html --out dist/velocity-report.html" is run
    - Then a standalone, zero-dependency HTML dashboard is generated with interactive charts and throughput forecasts.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Velocity reporter in `src/spec_ops/backlog/velocity/reporter.py` and rescue metrics aggregator in `src/spec_ops/backlog/velocity/rescue.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary commit timelines assert that velocity aggregates match the exact count of unique completed tasks in the evaluation window without double counting.
- **Mutmut Mutation Scope**: Cycle time calculations and rescue burden ratio logic in `src/spec_ops/backlog/velocity/reporter.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops report velocity` outputs human and agent delivery metrics with cycle times.
2. Executing `spec-ops report velocity --rescues` highlights failure clusters and rescue frequency.
3. Exporting reports to HTML/JSON produces valid, self-contained artifacts without external network dependencies.
4. All acceptance criteria verified via public CLI frontdoors with `pytest-bdd` (ADR-0003, ADR-0006).
