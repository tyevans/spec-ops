---
id: '0067'
title: Daily Curation Standup Digest and Stalled Claim Reclamation Engine
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
target_bc: backlog
---

# TASK-0067: Daily Curation Standup Digest and Stalled Claim Reclamation Engine

## Summary
Implement automated daily standup digest generation (`spec-ops queue digest [--format markdown|json]`), automated detection and reclamation of abandoned task claims (`spec-ops queue reclaim-stalled [--timeout-hours N]`), and clean milestone scope transitions across sprint and milestone boundaries.

## Problem Statement & Context
Engineering leads coordinating hybrid teams of human developers and autonomous AI agents require daily visibility into delivery throughput, blocked items, and ready buffer health without sifting manually through git history. Furthermore, when autonomous agent processes crash or abandon isolated worktrees, claimed tasks remain locked indefinitely in the backlog, blocking dependent work. SpecOps requires an automated standup digest generator and stale claim reclamation engine.

## User Stories & Scenarios Satisfied
- **US-0077: Daily Curation Standup Digest, Stalled Claim Detection, and Milestone Scope Transition**
  - *Scenario: Generating Daily Standup Curation Digest*
    - Given a repository with completed tasks in the last 24 hours, active in-progress worktree claims, and blocked proposed items
    - When the engineering lead runs "spec-ops queue digest"
    - Then the command outputs a formatted Markdown standup digest highlighting completed throughput, active worker leases, blocker bottlenecks, and ready buffer capacity.
  - *Scenario: Flagging and Reclaiming Abandoned Task Claims*
    - Given a task marked "In Progress" with a claim timestamp exceeding the configured timeout threshold (e.g. 4 hours) without heartbeat activity
    - When "spec-ops queue reclaim-stalled" is executed
    - Then the expired lease is revoked, the task status is safely returned to "Refined", and the event is logged to the curation audit trail.
  - *Scenario: Transitioning Backlog Scope Across Milestone Boundaries*
    - Given a completed milestone with remaining unworked tasks
    - When the curator runs "spec-ops milestone rollover --from M1 --to M2"
    - Then unfinished tasks are reassigned to the next milestone and milestone tags in frontmatter are atomically updated.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Standup digest generator in `src/spec_ops/backlog/digest.py` and lease reclamation engine in `src/spec_ops/backlog/reclaim.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary timestamp distributions assert that lease expiration logic is monotonic and never reclaims actively heartbeating worker leases.
- **Mutmut Mutation Scope**: Lease timeout and expiration calculations in `src/spec_ops/backlog/reclaim.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops queue digest` produces valid Markdown and structured JSON summaries.
2. Executing `spec-ops queue reclaim-stalled` releases expired leases cleanly and resets tasks to Refined.
3. Milestone scope transitions update task frontmatter atomically without metadata corruption.
4. All acceptance criteria verified via public CLI frontdoors with `pytest-bdd` (ADR-0003, ADR-0006).
