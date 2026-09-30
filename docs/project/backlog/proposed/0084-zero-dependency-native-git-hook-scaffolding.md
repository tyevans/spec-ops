---
id: '0084'
title: Zero-Dependency Native Git Hook Scaffolding and Autonomous Worktree Guardrails
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0064
governing_adrs:
  - ADR-0001
  - ADR-0003
  - ADR-0005
  - ADR-0007
  - ADR-0008
governing_prds:
  - PRD-0005
governing_stories:
  - US-0072
target_bc: scaffold
---

# TASK-0084: Zero-Dependency Native Git Hook Scaffolding and Autonomous Worktree Guardrails

## Summary
Implement zero-dependency POSIX shell native git hook generation and automatic worktree propagation (`spec-ops scaffold hooks [--force]`). Install pre-commit and pre-push hooks that enforce strict feature branch backlog isolation (preventing direct commits to `docs/project/backlog/` on feature branches per ADR-0005), file length invariants (<500 lines per ADR-0002), and lockfile immutability without requiring third-party python hook frameworks.

## Problem Statement & Context
While tools like `pre-commit` exist, they introduce external Python virtual environments and framework overhead that slow down git commits and can fail in isolated subagent worktrees. Furthermore, autonomous worker streams operating in `.worktrees/` frequently forget or fail to configure hooks, risking inadvertent commits to shared backlog indexes like `PRIORITY.md`. SpecOps requires fast, native POSIX shell hooks installed directly in `.git/hooks/` that are automatically propagated to all created worktrees.

## User Stories & Scenarios Satisfied
- **US-0072: Zero-Dependency Native Git Hook Scaffolding and Autonomous Worktree Guardrails**
  - *Scenario: Scaffolding native git pre-commit and pre-push hooks*
    - Given a Git repository initialized with SpecOps
    - When the developer runs "spec-ops scaffold hooks"
    - Then executable POSIX shell scripts are installed in ".git/hooks/pre-commit" and ".git/hooks/pre-push".
  - *Scenario: Enforcing strict backlog isolation on feature branches via hook*
    - Given a developer or agent on a branch "feat/my-feature"
    - When they attempt to commit modifications to "docs/project/backlog/PRIORITY.md"
    - Then the pre-commit hook aborts the commit with an explanatory error referencing ADR-0005.
  - *Scenario: Propagating hooks automatically to autonomous worker worktrees*
    - Given newly scaffolded native hooks in the parent repository
    - When an autonomous worker worktree is spawned
    - Then hooks are active and enforce invariants within the isolated worktree.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Native hook generator and installer in `src/spec_ops/scaffold/native_hooks.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary git branch names and staged file paths assert that hook script generators produce valid POSIX-compliant shell scripts without bashisms or unescaped variables.
- **Mutmut Mutation Scope**: Shell template rendering and hook path resolution in `src/spec_ops/scaffold/native_hooks.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops scaffold hooks` installs executable shell scripts into `.git/hooks/pre-commit` and `.git/hooks/pre-push`.
2. Attempting to commit changes to `docs/project/backlog/` on any non-main branch triggers pre-commit failure with exit code 1.
3. Pre-commit hook runs `spec-ops health` and blocks commit if any source file exceeds 500 lines.
4. Spawning a new worktree automatically links or configures hooks so that in-worktree commits are governed identically.
5. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
