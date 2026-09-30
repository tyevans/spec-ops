---
id: '0067'
title: Daily Curation Standup Digest, Stalled Claim Detection, and External Issue Tracker Bridge
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0066
governing_adrs:
  - ADR-0001
  - ADR-0003
  - ADR-0005
  - ADR-0007
governing_prds:
  - PRD-0005
governing_stories:
  - US-0077
  - US-0079
  - US-0022
  - US-0023
  - US-0025
target_bc: backlog
---

# TASK-0067: Daily Curation Standup Digest, Stalled Claim Detection, and External Issue Tracker Bridge

## Summary
Implement living backlog reporting, hybrid team telemetry, and external issue integration: author daily standup curation digest generation (`spec-ops queue digest [--format markdown|json]`), automatic stalled worker claim detection and lease reclamation (`spec-ops queue reclaim-stalled`), interactive milestone planning and workload simulation (`spec-ops milestone plan`), hybrid team velocity and autonomous worker rescue analytics (`spec-ops report velocity`), automated executive milestone briefings (`spec-ops report milestone`), and external issue tracker ingestion and bidirectional synchronization for GitHub Issues, Linear, and Jira (`spec-ops bridge import/export`).

## Problem Statement & Context
Engineering leads coordinating hybrid teams of human developers and autonomous AI agents require daily visibility into delivery throughput, stalled tasks, and rescue frequency without digging through git logs. When autonomous agents encounter insurmountable hurdles or crash, their claimed tasks remain locked indefinitely unless automatically reclaimed. Furthermore, enterprise organizations frequently rely on external issue trackers (GitHub Issues, Jira, Linear); lacking bi-directional ingestion and export tools isolates PMaC git specifications from executive stakeholders. SpecOps requires automated standup digests, lease reclamation, velocity reporting, and external issue bridging.

## User Stories & Scenarios Satisfied
- **US-0077: Daily Curation Standup Digest, Stalled Claim Detection, and Milestone Scope Transition**
  - *Scenario: Generating Daily Standup Curation Digest*
  - *Scenario: Flagging and Reclaiming Abandoned Task Claims*
  - *Scenario: Transitioning Backlog Scope Across Milestone Boundaries*
- **US-0079: Brownfield Issue Ingestion and External Backlog Synchronization Bridge**
  - *Scenario: Ingesting GitHub Issues into Validated Proposed Task Files*
  - *Scenario: Ingesting Structured CSV/JSON Export from Jira or Linear*
  - *Scenario: Bi-directional Export of Backlog Status for Executive Roadmaps*
- **US-0022: Hybrid Team Velocity and Autonomous Agent Rescue Analytics**
  - *Scenario: Generating Hybrid Velocity and Throughput Metrics*
  - *Scenario: Visualizing Rescue Burden and Failure Clustering*
  - *Scenario: Exporting Velocity Trends for Executive Reviews*
- **US-0023: Automated Executive Milestone Briefing and Roadmap Alignment Digest**
  - *Scenario: Generating Milestone Executive Summary*
  - *Scenario: Detecting Unanchored Scope Creep against Roadmap*
  - *Scenario: Standalone Executive HTML One-Pager*
- **US-0025: Interactive Milestone Planning and Workload Balancing Studio**
  - *Scenario: Allocating Tasks to Milestones and Execution Profiles*
  - *Scenario: Simulating Delivery Horizon and Bottleneck Feasibility*
  - *Scenario: Atomic Synchronization to Repository Markdown*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Standup digest generator in `src/spec_ops/backlog/digest.py`, milestone planner in `src/spec_ops/backlog/milestone.py`, velocity reporter in `src/spec_ops/backlog/velocity.py`, and external bridge in `src/spec_ops/backlog/bridge.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomized issue payloads assert that external issue imports strictly generate valid proposed task Markdown with non-colliding IDs and valid frontmatter schemas.
- **Mutmut Mutation Scope**: Stalled lease expiration calculation in `src/spec_ops/backlog/digest.py` and milestone feasibility projection in `src/spec_ops/backlog/milestone.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops queue digest` produces a Markdown and JSON summary of completed tasks, active worktree claims, blocker bottlenecks, and ready buffer waterlines.
2. Executing `spec-ops queue reclaim-stalled --timeout 4h` identifies task claims older than 4 hours with inactive worktrees and reverts their status to Refined.
3. Executing `spec-ops bridge import --github-issues <repo>` or `--jira <file.json>` converts external tickets into valid proposed tasks in `docs/project/backlog/proposed/`.
4. Executing `spec-ops bridge export --output roadmap.json` exports a structured roadmap payload suitable for external dashboard ingestion.
5. Executing `spec-ops report velocity` outputs human vs. agent throughput rates, rescue intervention percentages, and failure root-cause clustering.
6. Executing `spec-ops report milestone --milestone M1` generates an executive one-pager highlighting delivery burndown, scope creep, and projected completion date.
7. All acceptance criteria verified via public frontdoor `pytest-bdd` tests without mock backdoors (ADR-0003, ADR-0006).
