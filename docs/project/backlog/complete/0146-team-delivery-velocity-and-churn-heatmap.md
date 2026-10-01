---
id: '0146'
title: Team Delivery Velocity Engine and Cognitive Churn Heatmap
status: Complete
dependencies:
- TASK-0049
- TASK-0137
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0008
governing_prds:
- PRD-0005
governing_stories:
- US-0049
- US-0052
target_bc: release
---

# TASK-0146: Team Delivery Velocity Engine and Cognitive Churn Heatmap

## Summary
Implement the team delivery velocity engine and cognitive churn heatmap (`spec-ops release velocity [--format markdown|html|json]`). Fulfilling PRD-0005 and ADR-0008, this engine correlates git commit cadence, worktree completion durations, and file modification churn to compute team velocity metrics, detect developer cognitive bottlenecks, and highlight high-churn files prone to architectural rot.

## Problem Statement & Context
Engineering leads and architects require visibility into delivery cadence and technical debt accumulation across bounded contexts. Tracking only completed task counts obscures the fact that certain modules suffer extreme edit churn, high retry rates, or prolonged worktree durations. An autonomous velocity and churn heatmap surfaces these architectural friction points automatically.

## Key Requirements & Scope
1. **Velocity and Churn Analysis (`src/spec_ops/release/velocity_heatmap.py`)**:
   - Analyzes git commit logs and completed task metadata to compute throughput (tasks per milestone/week) and lead time.
   - Calculates file churn: identifies source files with disproportionate commit frequencies or high lines-changed volatility.
   - Generates cognitive load heatmaps flagging modules approaching complexity thresholds.
2. **Multi-Format Reporting**:
   - Formats outputs in terminal tables, self-contained HTML reports with visual heatmaps, or structured JSON.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Velocity heatmap module in `src/spec_ops/release/velocity_heatmap.py` must stay strictly under 400 lines (ADR-0002).
- **Diataxis Compliance (ADR-0008)**: Outputs and documentation adhere strictly to Diataxis reporting standards.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/release/velocity_heatmap.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Computing delivery velocity metrics from git history
```gherkin
Given a project repository with completed tasks and git commits
When the engineering lead executes "spec-ops release velocity"
Then a delivery velocity report is generated
And displays task completion rates, lead time, and high-churn source files
```

### Scenario 2: Exporting standalone HTML churn heatmap
```gherkin
Given completed project delivery milestones
When the user runs "spec-ops release velocity --format html"
Then a standalone HTML heatmap report is generated
And visualizes file modification churn without external CDN dependencies
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary sequence of commit records and task durations, calculated velocity metrics and churn scores remain non-negative and mathematically valid.
