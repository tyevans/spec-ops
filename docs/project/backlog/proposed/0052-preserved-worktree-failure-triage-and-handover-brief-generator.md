---
id: '0052'
title: Interactive Preserved Worktree Failure Triage, Diagnostic Breakdown, and HANDOVER.md Brief Generator
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0047
  - TASK-0051
governing_adrs:
  - ADR-0002
  - ADR-0003
  - ADR-0004
  - ADR-0005
  - ADR-0007
  - ADR-0009
governing_prds:
  - PRD-0004
governing_stories:
  - US-0087
  - US-0090
  - US-0035
target_bc: rescue
---

# TASK-0052: Interactive Preserved Worktree Failure Triage, Diagnostic Breakdown, and HANDOVER.md Brief Generator

## Summary
Implement automated generation of structured AI-to-human handover briefs (`.worktrees/<task-id>/HANDOVER.md`) upon agent self-healing exhaustion, interactive failure triage via `spec-ops rescue triage <task-id>` with categorized root-cause breakdowns, and terminal developer cheatsheets with instant reproducer commands. Ensure ephemeral handover briefs are automatically purged before production git staging.

## Problem Statement & Context
When an autonomous coding agent exhausts its retry budget, human developers stepping in to rescue the task are confronted with an undifferentiated "wall of terminal text" and must guess what the agent attempted, which test or invariant failed, and how to reproduce the error. Without structured triage and categorized diagnostics, human takeover is slow, error-prone, and frustrating.

## User Stories & Scenarios Satisfied
- **US-0087: Interactive Preserved Worktree Triage and Failure Diagnostic Breakdown**
  - *Scenario: Categorizing preflight failure modes in a stalled worktree*
  - *Scenario: Inspecting AST and line count diffs per modified file*
  - *Scenario: Navigating directly to recommended rescue actions*
- **US-0090: Preserved Worktree AI-to-Human Handover Brief and Debug Cheatsheet**
  - *Scenario: Automatic generation of HANDOVER.md upon agent exhaustion*
  - *Scenario: Terminal cheatsheet display upon running rescue inspection*
  - *Scenario: Ensuring HANDOVER.md is excluded from production commits*
- **US-0035: Stalled Autonomous Worktree Inspection and Diagnostic Takeover**
  - *Scenario: Inspecting a stalled agent worktree with diagnostics*
  - *Scenario: Human takeover, verification, and atomic merge into main*
  - *Scenario: Discarding an irreparably broken agent worktree*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Triage diagnostic engine in `src/spec_ops/rescue/triage.py` and handover generator in `src/spec_ops/rescue/handover.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary preflight failure logs and exit codes assert that categorized failure breakdowns accurately isolate file-length, test, lockfile, and working tree errors into distinct non-overlapping diagnostic categories.
- **Mutmut Mutation Scope**: Diagnostic parsing in `src/spec_ops/rescue/triage.py` and handover generation in `src/spec_ops/rescue/handover.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. When an agent exhausts self-healing attempts, the worker engine generates `.worktrees/<task-id>/HANDOVER.md` containing attempt timeline, isolated failure traceback, governing PRD/ADR links, exact reproduction command, and completion command.
2. Executing `spec-ops rescue triage <task-id>` displays a categorized diagnostic summary (File Length, Test Suite, Lockfile, Working Tree State) and launches an interactive menu (`[d]iff`, `[p]atch`, `[s]hell`, `[r]eset`, `[c]omplete`, `[q]uit`).
3. Selecting diff in triage displays syntax-highlighted git diffs with net line delta and remaining headroom to the 500-line invariant limit.
4. Executing `spec-ops rescue <task-id>` displays the copy-paste developer cheatsheet with commands to cd into worktree, reproduce failure, inspect diffs, complete rescue, or discard.
5. Executing `spec-ops rescue <task-id> --complete` automatically purges `HANDOVER.md` and `.task-prompt.md` prior to staging, ensuring zero handover artifacts enter git history.
6. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
