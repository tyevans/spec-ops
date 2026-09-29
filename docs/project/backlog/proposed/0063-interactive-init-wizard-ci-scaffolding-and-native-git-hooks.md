---
id: '0063'
title: Interactive Guided Initialization Wizard, Multi-Platform CI Scaffolding, and Zero-Dependency Native Git Hooks
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0062
  - TASK-0012
governing_adrs:
  - ADR-0001
  - ADR-0003
  - ADR-0004
  - ADR-0005
  - ADR-0007
  - ADR-0008
governing_prds:
  - PRD-0005
governing_stories:
  - US-0066
  - US-0069
  - US-0072
  - US-0071
target_bc: scaffold
---

# TASK-0063: Interactive Guided Initialization Wizard, Multi-Platform CI Scaffolding, and Zero-Dependency Native Git Hooks

## Summary
Deliver end-to-end repository onboarding and developer experience scaffolding: author an interactive terminal initialization wizard (`spec-ops init --interactive`) featuring live configuration previews alongside an unattended headless mode (`spec-ops init --headless --profile <p>`), scaffold multi-platform CI pipelines for GitHub Actions and GitLab CI (`spec-ops scaffold ci --platform all`), generate zero-dependency native POSIX git hooks enforcing pre-commit line limits and feature branch backlog isolation (`spec-ops scaffold hooks`), and scaffold Diataxis documentation quadrants for new bounded contexts with embedded living visualizer links (`spec-ops scaffold docs --bc <name>`).

## Problem Statement & Context
Onboarding new teams and repositories onto SpecOps requires configuring profiles, CI workflows, git hooks, and documentation structures. When setup requires multi-step manual edits across YAML and TOML files, teams experience friction, misconfigure hook paths, or skip CI preflight gates. Autonomous workers also require native git hooks inside isolated worktrees to prevent accidental commits to `PRIORITY.md` or violations of line-length invariants before pushing. SpecOps needs an interactive onboarding wizard, multi-platform CI scaffolding, and bulletproof native git hooks.

## User Stories & Scenarios Satisfied
- **US-0066: Interactive Guided Initialization Wizard and Headless CI Automation Scaffolding**
  - *Scenario: Interactive terminal onboarding wizard with live configuration preview*
  - *Scenario: Unattended headless initialization for CI and automation templates*
  - *Scenario: Initialization dry-run preview mode*
- **US-0069: Multi-Platform CI/CD Pipeline Scaffolding Across GitHub Actions and GitLab CI**
  - *Scenario: Scaffolding a GitLab CI quality pipeline*
  - *Scenario: Scaffolding multi-platform CI pipelines simultaneously*
  - *Scenario: Updating existing CI workflow on toolchain version bump*
- **US-0072: Zero-Dependency Native Git Hook Scaffolding and Autonomous Worktree Guardrails**
  - *Scenario: Scaffolding native git pre-commit and pre-push hooks*
  - *Scenario: Enforcing strict backlog isolation on feature branches via hook*
  - *Scenario: Propagating hooks automatically to autonomous worker worktrees*
- **US-0071: Bounded-Context Diataxis Documentation Scaffolding and Living Spec Linking**
  - *Scenario: Scaffolding Diataxis quadrant for a new bounded context*
  - *Scenario: Embedding deep links to the living 2D visualizer*
  - *Scenario: Preventing duplicate bounded context scaffolding*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Init wizard in `src/spec_ops/scaffold/wizard.py`, CI pipeline generator in `src/spec_ops/scaffold/ci_multi.py`, and hook installer in `src/spec_ops/scaffold/native_hooks.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomized configuration permutations assert that `spec-ops init --dry-run` and `spec-ops init` produce identical in-memory AST configurations, and that generated shell hooks contain valid POSIX-compliant syntax without bashisms.
- **Mutmut Mutation Scope**: Interactive prompt state handling in `src/spec_ops/scaffold/wizard.py` and hook template rendering in `src/spec_ops/scaffold/native_hooks.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops init --interactive` guides the user through profile selection, bounded context declaration, and CI platform choice with live formatted previews.
2. Executing `spec-ops init --headless --profile base` initializes a compliant project in under 2 seconds without interactive prompts, suitable for automated CI templates.
3. Executing `spec-ops scaffold ci --platform all` generates `.github/workflows/specops.yml` and `.gitlab-ci.yml` verifying `uv run spec-ops health` and `uv run pytest`.
4. Executing `spec-ops scaffold hooks` installs standalone executable POSIX shell scripts into `.git/hooks/` and configures automatic hook propagation to active worker worktrees.
5. In a feature branch worktree, attempting to commit modifications directly to `docs/project/backlog/PRIORITY.md` is rejected by the pre-commit hook with an explanatory error (ADR-0005).
6. Executing `spec-ops scaffold docs --bc <name>` generates Diataxis folders (`tutorials/`, `how-to/`, `reference/`, `explanation/`) with visualizer deep-link references.
7. All acceptance criteria verified via public frontdoor `pytest-bdd` tests without mock backdoors (ADR-0003, ADR-0006).
