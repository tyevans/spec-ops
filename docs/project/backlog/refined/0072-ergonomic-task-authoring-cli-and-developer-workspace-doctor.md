---
id: '0072'
title: Ergonomic Task Authoring CLI and Developer Workspace Onboarding Doctor
status: Refined
dependencies:
- TASK-0007
- TASK-0044
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0008
- ADR-0009
governing_prds:
- PRD-0004
governing_stories:
- US-0039
- US-0042
target_bc: worker
---

# TASK-0072: Ergonomic Task Authoring CLI and Developer Workspace Onboarding Doctor

## Summary
Implement ergonomic CLI task authoring with interactive Definition of Ready validation (`spec-ops task create`) and a one-command developer environment diagnostic and automated onboarding repair tool (`spec-ops doctor [--fix]`).

## Problem Statement & Context
Developers authoring PMaC tasks manually often omit required frontmatter fields (such as governing stories, ADRs, or target bounded contexts), causing validation errors later in the lifecycle. Additionally, developers onboarding to SpecOps need a fast diagnostic doctor to audit local tooling (UV, git hooks, ignore files) and automatically configure their workspace in under 60 seconds.

## User Stories & Scenarios Satisfied
- **US-0039: Ergonomic Human Task and Bug Authoring with Definition of Ready Scaffolding**
  - *Scenario: Scaffolding a new proposed task via CLI flags*
  - *Scenario: Definition of Ready (DoR) validation when promoting to refined*
- **US-0042: One-Command Developer Environment Doctor and Workspace Onboarding**
  - *Scenario: Diagnostic audit of local developer tooling and workspace health*
  - *Scenario: Automated repair of missing hooks and configuration*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Task authoring in `src/spec_ops/cli/task_handler.py` and doctor in `src/spec_ops/rescue/doctor.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that `spec-ops task create` generates valid YAML frontmatter roundtrippable by `SpecOpsParser` with zero unparsed fields.
- **Mutmut Mutation Scope**: Task scaffolding validation and doctor repair routines achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops task create --title <t> --bc <bc> --prd <prd> --story <us>` scaffolds a valid proposed task file and updates `PRIORITY.md`.
2. Promoting a task via `spec-ops queue refine` blocks if Definition of Ready (DoR) is unsatisfied.
3. Executing `spec-ops doctor` audits UV workspace, worktrees gitignore, pre-commit hooks, and line limit health; passing `--fix` installs missing hooks and auto-configures the environment.
4. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
