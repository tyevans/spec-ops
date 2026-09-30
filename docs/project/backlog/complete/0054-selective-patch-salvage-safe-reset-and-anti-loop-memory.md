---
id: '0054'
title: Selective Patch Takeover and Partial File Salvage from Stalled Worktrees
status: Complete
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
target_bc: rescue
---

# TASK-0054: Selective Patch Takeover and Partial File Salvage from Stalled Worktrees

## Summary
Implement selective patch takeover via `spec-ops rescue patch <task-id> --include <file>` to stage viable source and test files while excluding untracked scratchpad and bloated modules, run preflight validation on the curated patch, and squash-merge into `main` with dual-custody provenance trailers (`SpecOps-Task`, `Author`, `Rescued-By`, `Provenance: agent-human-hybrid`).

## Problem Statement & Context
When an autonomous worker stalls, 80% of its work may be perfectly valid, while 20% contains hallucinations, bloated code, or scratch files. Naive `git add -A` inherits all messy baggage, while abandoning the worktree throws away expensive LLM compute. Developers need a mechanism to cherry-pick only high-quality files from a stalled worktree, validate them with preflight checks, and merge them cleanly into `main`.

## User Stories & Scenarios Satisfied
- **US-0088: Selective Patch Takeover and Partial File Salvage from Stalled Worktrees**
  - *Scenario: Selectively cherry-picking valid domain files while discarding hallucinated scrap*
    - Given a stalled worktree containing clean domain models alongside oversized tests and scratch files
    - When the developer runs `spec-ops rescue patch <task-id> --include src/model.py`
    - Then only the specified file is staged into the curated patch.
  - *Scenario: Preflight verification of the selectively salvaged patch*
    - Given a curated staging patch
    - When `spec-ops rescue <task-id> --complete --salvage` executes
    - Then preflight verification runs exclusively against staged files.
  - *Scenario: Squash-merging salvaged patch into main with dual-custody provenance trailers*
    - Given passing preflight on the salvaged patch
    - When the merge completes
    - Then `main` receives a clean commit with trailers attributing both the original agent and the human rescuer.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Patch salvage manager in `src/spec_ops/rescue/salvage.py` stays strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly generated file selection lists assert that only explicitly included files are staged into the git index and unselected files are strictly excluded from preflight verification and commit trees.
- **Mutmut Mutation Scope**: Selective staging in `src/spec_ops/rescue/salvage.py` achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops rescue patch <task-id> --include <path>` stages only the specified files; untracked scratch files and unselected bloated modules remain uncommitted.
2. Executing `spec-ops rescue <task-id> --complete --salvage` executes preflight verification solely against the curated staging area.
3. Upon preflight passing, the rescue manager squash-merges the salvaged patch into `main` under `MERGE_LOCK` with dual-custody trailers (`SpecOps-Task: TASK-XXXX`, `Author: Morgan`, `Rescued-By: Riley`, `Provenance: agent-human-hybrid`).
4. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
