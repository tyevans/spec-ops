---
id: '0044'
title: Machine-Readable Task Contracts, Backlog Protection Guardrails, and Autonomous
  Claim Gates
status: Complete
dependencies:
- TASK-0007
- TASK-0011
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0006
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0004
governing_stories:
- US-0027
- US-0030
- US-0031
target_bc: worker
allows_dependencies: true
---

# TASK-0044: Machine-Readable Task Contracts, Backlog Protection Guardrails, and Autonomous Claim Gates

## Summary
Implement the autonomous task claim engine (`spec-ops worker claim --auto`) with strict Definition of Ready (DoR) gatekeeping, automated in-worktree contract hydration generating `.task-prompt.md`, and silent backlog protection guardrails that detect and revert accidental modifications to `docs/project/backlog/` before staging and git commit.

## Problem Statement & Context
Autonomous coding agents lack deterministic context hydration upon entering an isolated worktree, frequently hallucinating repo conventions, ignoring modular line limits, or missing quality gates. Furthermore, parallel agents frequently make unintended edits to shared backlog management files (`PRIORITY.md` or task markdown specs) within their feature worktrees, causing merge conflicts and violating ADR-0005. SpecOps requires an automated claim gate that guarantees tasks are ready, hydrates unambiguous task contracts, and protects the shared backlog index.

## User Stories & Scenarios Satisfied
- **US-0027: Machine-Readable Task Contract and Architectural Context Hydration**
  - *Scenario: Hydrating Task Contract into Worktree Environment*
- **US-0030: Automated Backlog Protection and Accidental Modification Guardrails**
  - *Scenario: Intercepting and Reverting Accidental Backlog Changes*
- **US-0031: Autonomous Task Claiming with Dependency and Definition of Ready Gate**
  - *Scenario: Successfully Claiming Highest-Priority Ready Task*
  - *Scenario: Blocking Claim on Incomplete Task Dependencies*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Claim and prompt hydration logic in `src/spec_ops/worker/claimer.py` and backlog guardrails in `src/spec_ops/worker/guardrails.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary git staging states and backlog tree mutations assert that `guardrails.sanitize_backlog_modifications()` deterministically detects any dirty files under `docs/project/backlog/`, executes `git checkout HEAD`, and ensures git commit payloads contain 0 modifications to shared backlog indices.
- **Mutmut Mutation Scope**: Core claiming logic, DoR validation, and prompt hydration in `src/spec_ops/worker/claimer.py` and `src/spec_ops/worker/guardrails.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops worker claim --auto` evaluates `docs/project/backlog/PRIORITY.md` in strict priority order, skips blocked tasks with unsatisfied dependencies, verifies DoR (valid PRD link, governing ADRs, Gherkin scenarios), provisions worktree `.worktrees/<task-id>`, and exits with code 0 and JSON task metadata.
2. Initializing a worktree automatically generates `.task-prompt.md` containing the 500-line file length limit invariant, frontdoor blackbox testing rules with zero private mocks, and exact preflight command chain (`uv lock --check && uv run pytest && uv run spec-ops health`).
3. If an agent modifies files under `docs/project/backlog/`, the worker engine intercepts staged files, reverts backlog modifications via `git checkout HEAD docs/project/backlog/`, and stages only functional code and tests.
4. All acceptance criteria verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
