---
id: '0104'
title: Safe Worktree Discard with Anti-Loop Failure Memory and Task Reset
status: Complete
dependencies:
- TASK-0053
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0005
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0004
governing_stories:
- US-0089
target_bc: rescue
---

# TASK-0104: Safe Worktree Discard with Anti-Loop Failure Memory and Task Reset

## Summary
Implement safe worktree discarding with anti-loop failure memory and task reset (`spec-ops rescue reset <task-id> --reason <text> [--demote]`): safely destroy the worktree while persisting structured failure history into task frontmatter and injecting negative prompt constraints into subsequent worker iterations.

## Problem Statement & Context
When discarding an unrecoverable worktree, failure to document why the attempt failed dooms subsequent autonomous coding agents to repeat the exact same errors in an infinite loop. When an agent produces hallucinated architectures or repeatedly fails invariant checks, the system must capture this post-mortem history directly in the task specification and inject explicit negative constraints ("DO NOT REPEAT") into future worker prompt hydration.

## User Stories & Scenarios Satisfied
- **US-0089: Safe Worktree Discard with Anti-Loop Failure Memory and Task Reset**
  - *Scenario: Discarding worktree and capturing failure post-mortem into task frontmatter*
    - Given an unrecoverable worktree in `.worktrees/`
    - When the developer runs `spec-ops rescue reset <task-id> --reason "Oversized architecture"`
    - Then the worktree is safely deleted and the reason is recorded in task frontmatter `failure_history`.
  - *Scenario: Automatic demotion to proposed stage when specification ambiguity is flagged*
    - Given a task reset with the `--demote` flag
    - When the reset executes
    - Then the task file is moved from `refined/` back to `proposed/`.
  - *Scenario: Hydrating subsequent worker prompts with negative constraints from failure history*
    - Given a task with recorded `failure_history`
    - When a new worker claims the task
    - Then prompt hydration injects a negative constraint section warning the agent against previously failed patterns.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Anti-loop memory manager in `src/spec_ops/rescue/memory.py` stays strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that repeated resets monotonically append to `failure_history` without overwriting prior attempt entries or corrupting other frontmatter fields.
- **Mutmut Mutation Scope**: Failure history recording and prompt constraint generation in `src/spec_ops/rescue/memory.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops rescue reset <task-id> --reason <text>` wipes the worktree and branch, appends failure details to task `failure_history`, and updates `PRIORITY.md`.
2. Passing `--demote` automatically moves the task file from `refined/` to `proposed/`.
3. Subsequent claims hydrate worker prompts with a `## Prior Attempt Failures & Anti-Patterns (DO NOT REPEAT)` section containing explicit negative constraints.
4. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
