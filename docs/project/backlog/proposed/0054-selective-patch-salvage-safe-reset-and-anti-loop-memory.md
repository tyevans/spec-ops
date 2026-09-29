---
id: '0054'
title: Selective Patch Salvage, Safe Worktree Reset, and Anti-Loop Memory Enforcement
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0048
  - TASK-0053
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0005
  - ADR-0007
  - ADR-0009
governing_prds:
  - PRD-0004
governing_stories:
  - US-0088
  - US-0089
target_bc: rescue
---

# TASK-0054: Selective Patch Salvage, Safe Worktree Reset, and Anti-Loop Memory Enforcement

## Summary
Implement selective patch takeover via `spec-ops rescue patch <task-id> --include <file>` to stage viable source and test files while excluding untracked scratchpad and bloated modules, run preflight validation on the curated patch, and squash-merge into `main` with dual-custody provenance trailers (`SpecOps-Task`, `Author`, `Rescued-By`, `Provenance: agent-human-hybrid`). Implement `spec-ops rescue reset <task-id> --reason <text> [--demote]` to safely destroy the worktree while persisting failure history into task frontmatter and injecting negative constraints into future worker prompt hydration.

## Problem Statement & Context
When an autonomous worker stalls, 80% of its work may be perfectly valid, while 20% contains hallucinations, bloated code, or scratch files. Naive `git add -A` inherits all messy baggage, while abandoning the worktree throws away expensive LLM compute. Furthermore, when discarding an unrecoverable worktree, failure to document why the attempt failed dooms subsequent agents to repeat the exact same errors in an infinite loop.

## User Stories & Scenarios Satisfied
- **US-0088: Selective Patch Takeover and Partial File Salvage from Stalled Worktrees**
  - *Scenario: Selectively cherry-picking valid domain files while discarding hallucinated scrap*
  - *Scenario: Preflight verification of the selectively salvaged patch*
  - *Scenario: Squash-merging salvaged patch into main with dual-custody provenance trailers*
- **US-0089: Safe Worktree Discard with Anti-Loop Failure Memory and Task Reset**
  - *Scenario: Discarding worktree and capturing failure post-mortem into task frontmatter*
  - *Scenario: Automatic demotion to proposed stage when specification ambiguity is flagged*
  - *Scenario: Hydrating subsequent worker prompts with negative constraints from failure history*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Patch salvage manager in `src/spec_ops/rescue/salvage.py` and anti-loop memory manager in `src/spec_ops/rescue/memory.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly generated file selection lists assert that only explicitly included files are staged into the git index and unselected files are strictly excluded from preflight verification and commit trees.
- **Mutmut Mutation Scope**: Selective staging in `src/spec_ops/rescue/salvage.py` and failure history recording in `src/spec_ops/rescue/memory.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops rescue patch <task-id> --include <path>` stages only the specified files; untracked scratch files and unselected bloated modules remain uncommitted and out of preflight.
2. Executing `spec-ops rescue <task-id> --complete --salvage` executes preflight verification solely against the curated staging area.
3. Upon preflight passing, the rescue manager squash-merges the salvaged patch into `main` under `MERGE_LOCK` with dual-custody trailers (`SpecOps-Task: TASK-XXXX`, `Author: Morgan`, `Rescued-By: Riley`, `Provenance: agent-human-hybrid`).
4. Executing `spec-ops rescue reset <task-id> --reason <text>` wipes the worktree and branch, appends the failure reason and failed invariants to the task's `failure_history` frontmatter, and updates `PRIORITY.md`.
5. Passing `--demote` automatically moves the task file from `refined/` to `proposed/`.
6. Subsequent claims of the task hydrate `.task-prompt.md` with a `## Prior Attempt Failures & Anti-Patterns (DO NOT REPEAT)` section containing explicit negative constraints.
7. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
