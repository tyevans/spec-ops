---
id: 0097
title: Preserved Worktree AI-to-Human Handover Brief and Debug Cheatsheet Generator
status: Refined
dependencies:
- TASK-0052
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0004
- ADR-0005
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0004
governing_stories:
- US-0090
target_bc: rescue
claimed_by: worker-2
branch: feat/0097-preserved-worktree-ai-to-human-handover-
---

# TASK-0097: Preserved Worktree AI-to-Human Handover Brief and Debug Cheatsheet Generator

## Summary
Implement automated generation of structured AI-to-human handover briefs (`.worktrees/<task-id>/HANDOVER.md`) upon autonomous agent exhaustion, interactive terminal cheatsheet rendering with exact reproducer commands, and automated exclusion of ephemeral handover briefs from production git commits.

## Problem Statement & Context
When an autonomous coding agent exhausts its retry attempts, human developers need an immediate, standardized handover brief explaining what the agent attempted, which exact invariant failed, and copy-pasteable terminal commands to reproduce and diagnose the failure. Without structured handover documents, developers spend valuable time piecing together context from verbose logs.

## User Stories & Scenarios Satisfied
- **US-0090: Preserved Worktree AI-to-Human Handover Brief and Debug Cheatsheet**
  - *Scenario: Automatic generation of HANDOVER.md upon agent exhaustion*
    - Given an autonomous agent fails preflight after exhausting retries
    - When the worker engine preserves the worktree
    - Then `.worktrees/<task-id>/HANDOVER.md` is generated with task metadata, failed invariant, and reproducer commands.
  - *Scenario: Terminal cheatsheet display upon running rescue inspection*
    - Given a preserved worktree containing HANDOVER.md
    - When "spec-ops rescue inspect <task-id>" runs
    - Then a high-contrast terminal cheatsheet summarizes failure causes and next steps.
  - *Scenario: Ensuring HANDOVER.md is excluded from production commits*
    - Given a worktree containing HANDOVER.md
    - When changes are staged or integrated
    - Then HANDOVER.md is strictly excluded from git staging and production commits.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Handover brief generator in `src/spec_ops/rescue/handover.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that generated `HANDOVER.md` files never contain unescaped credentials or secrets and are ignored by git status.
- **Mutmut Mutation Scope**: Markdown template formatting and exclusion filters in `src/spec_ops/rescue/handover.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Worker failure exhaustion automatically generates `.worktrees/<task-id>/HANDOVER.md` with structured diagnostics and reproducer commands.
2. `spec-ops rescue inspect <task-id>` displays the formatted handover brief in the terminal.
3. Preflight and commit gates assert that `HANDOVER.md` is never staged or committed to git.
4. All scenarios verified via public frontdoors using `pytest-bdd` without mock backdoors (ADR-0003, ADR-0006).
