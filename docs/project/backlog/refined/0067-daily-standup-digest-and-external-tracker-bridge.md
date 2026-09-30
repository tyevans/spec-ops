---
id: '0067'
title: Daily Curation Standup Digest Generator
status: Refined
dependencies:
- TASK-0066
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0077
target_bc: backlog
---

# TASK-0067: Daily Curation Standup Digest Generator

## Summary
Implement automated daily standup digest generation (`spec-ops queue digest [--format markdown|json] [--window 24h]`), summarizing completed throughput, active worker worktree leases, blocker bottlenecks, and ready buffer capacity without requiring manual git inspection.

## Problem Statement & Context
Engineering leads and architects coordinating hybrid teams of human developers and autonomous AI agents require daily visibility into delivery throughput, blocked items, and ready buffer health without sifting manually through commit histories. SpecOps requires an automated standup digest generator that synthesizes the current state of the backlog into actionable Markdown and structured JSON summaries.

## User Stories & Scenarios Satisfied
- **US-0077: Daily Curation Standup Digest, Stalled Claim Detection, and Milestone Scope Transition**
  - *Scenario: Generating Daily Standup Curation Digest*
    - Given a repository with completed tasks in the last 24 hours, active in-progress worktree claims, and blocked proposed items
    - When the engineering lead runs "spec-ops queue digest"
    - Then the command outputs a formatted Markdown standup digest highlighting completed throughput, active worker leases, blocker bottlenecks, and ready buffer capacity.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Standup digest generator in `src/spec_ops/backlog/digest.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly generated task queues assert that digest metrics accurately sum task counts across statuses with zero double-counting.
- **Mutmut Mutation Scope**: Digest serialization and status filtering algorithms in `src/spec_ops/backlog/digest.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops queue digest` produces valid Markdown and structured JSON summaries.
2. Output correctly categorizes completed throughput, active worker leases, and ready buffer health.
3. All acceptance criteria verified via public CLI frontdoors with `pytest-bdd` (ADR-0003, ADR-0006).
