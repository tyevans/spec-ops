---
id: 0028
title: Supply-Chain Lockfile Verification and Slopsquatting Defense Gate
status: Refined
dependencies:
- TASK-0019
- TASK-0027
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0004
- ADR-0005
governing_prds:
- PRD-0002
governing_stories:
- US-0053
- US-0111
target_bc: security
claimed_by: worker-3
branch: feat/0028-supply-chain-lockfile-verification-and-s
---

# TASK-0028: Supply-Chain Lockfile Verification and Slopsquatting Defense Gate

## Summary
Enforce strict dependency lockfile immutability and cryptographic package hash verification. Validate that only tasks declaring `allows_dependencies: true` in task frontmatter are permitted to alter `pyproject.toml` or `uv.lock`. Provide CLI command `spec-ops security verify-lock` to detect unpinned, drifted, or hallucinated packages ("slopsquatting") and gate `spec-ops queue complete` against unauthorized branch diffs.

## Problem Statement & Context
LLMs frequently hallucinate nonexistent package dependencies or attempt to solve tasks by installing unvetted external libraries from PyPI. Threat actors exploit this behavior by publishing malicious packages matching common AI hallucinations ("slopsquatting"). Autonomous worktrees must reject lockfile and dependency alterations by default, and verify upstream cryptographic hashes whenever dependency updates are explicitly authorized.

## User Stories & Scenarios Satisfied
- **US-0053: Immutable Supply-Chain Lockfile Verification and Slopsquatting Defense**
  - *Scenario*: Rejecting unauthorized dependency additions in task worktrees
  - *Scenario*: Cryptographic hash verification for authorized dependency tasks
- **US-0111: Immutable Supply-Chain Lockfile Verification and Slopsquatting Defense**
  - *Scenario*: Rejecting unauthorized dependency additions in task worktrees
  - *Scenario*: Cryptographic hash verification for authorized dependency tasks
  - *Scenario*: Integration gate verifies lockfile immutability across the branch diff

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Isolate lockfile verification algorithms in `src/spec_ops/security/lockfile.py` and integration gates in `src/spec_ops/backlog/queue.py`, ensuring all source files stay below 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property testing using `@given(...)` across permutations of task frontmatter metadata and file diff trees verifies that any modification touching `pyproject.toml` or `uv.lock` without `allows_dependencies: true` strictly fails the validation gate.
- **Mutmut Mutation Scope**: Lockfile inspection and hash verification checks in `src/spec_ops/security/lockfile.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. In-worktree preflight halts with an "Unauthorized Dependency Modification" violation if `pyproject.toml` or `uv.lock` is modified for any task lacking `allows_dependencies: true`.
2. When `allows_dependencies: true` is set, `spec-ops security verify-lock` executes `uv lock --check`, asserting all package hashes match upstream cryptographic records, failing with returncode 1 on drift or unpinned packages.
3. Integration gate `spec-ops queue complete <task-id>` verifies that the branch diff against `main` contains zero unauthorized lockfile changes under merge lock.
4. Acceptance criteria verified via executable `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
