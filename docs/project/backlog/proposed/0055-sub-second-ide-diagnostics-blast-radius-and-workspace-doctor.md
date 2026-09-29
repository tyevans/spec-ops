---
id: '0055'
title: Sub-Second IDE Invariant Diagnostics, Deep-Linked Blast Radius, and Workspace Doctor
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0013
  - TASK-0015
  - TASK-0046
  - TASK-0052
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0007
  - ADR-0008
  - ADR-0009
governing_prds:
  - PRD-0004
governing_stories:
  - US-0091
  - US-0093
  - US-0039
  - US-0040
  - US-0041
  - US-0042
target_bc: rescue
---

# TASK-0055: Sub-Second IDE Invariant Diagnostics, Deep-Linked Blast Radius, and Workspace Doctor

## Summary
Deliver rapid developer ergonomics and real-time IDE tooling: sub-50ms single-file invariant diagnostic checks (`spec-ops check --fast --file <path> [--format json|sarif]`), fast incremental in-worktree preflight runner with step isolation (`spec-ops rescue test --step <step> [--only-failed]`), ergonomic CLI task authoring with interactive Definition of Ready validation (`spec-ops task create`), deep-linked 2D visualizer blast radius inspection (`spec-ops visualizer --serve --entity <id>`), automated Diataxis documentation drift detection (`spec-ops docs check`), and one-command local environment audit and repair (`spec-ops doctor [--fix]`).

## Problem Statement & Context
Human developers working alongside autonomous agents require rapid local iteration loops without waiting for slow preflight suites. Line length and bounded context import violations must be surfaced in real time in IDEs on file-save rather than at pre-commit or CI time. When rescuing worktrees, running minor 1-line fixes shouldn't trigger 5-minute test suites. Developers also need ergonomic CLI scaffolding to author compliant PMaC tasks, deep visualizer links to inspect blast radii during code review, documentation drift checks to maintain Diataxis standards, and an onboarding doctor to verify local setups in 60 seconds.

## User Stories & Scenarios Satisfied
- **US-0091: Sub-Second Incremental Invariant Diagnostics for Editor and IDE Feedback**
  - *Scenario: Blazing fast single-file invariant evaluation on save*
  - *Scenario: Immediate diagnostic error on hard invariant violation*
  - *Scenario: Bounded context boundary import validation*
- **US-0093: Fast Incremental In-Worktree Preflight Runner with Targeted Step Isolation**
  - *Scenario: Running isolated failed step with cached preflight results*
  - *Scenario: Rapid feedback cycle during local rescue iteration*
  - *Scenario: Enforcing mandatory full-suite revalidation upon rescue completion*
- **US-0039: Ergonomic Human Task and Bug Authoring with Definition of Ready Scaffolding**
  - *Scenario: Scaffolding a new proposed task via CLI flags*
  - *Scenario: Definition of Ready (DoR) validation when promoting to refined*
- **US-0040: Deep-Linked Visualizer Blast Radius Inspection During Code Review**
  - *Scenario: Launching the visualizer focused on a task entity*
  - *Scenario: Inspecting bounded context boundary isolation*
- **US-0041: Living Diataxis Documentation Drift Guard for IC Feature Work**
  - *Scenario: Detecting undocumented public CLI command additions*
  - *Scenario: Passing documentation check when Diataxis docs are synchronized*
- **US-0042: One-Command Developer Environment Doctor and Workspace Onboarding**
  - *Scenario: Diagnostic audit of local developer tooling and workspace health*
  - *Scenario: Automated repair of missing hooks and configuration*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Diagnostic evaluator in `src/spec_ops/rescue/fast_check.py`, step test runner in `src/spec_ops/rescue/incremental_runner.py`, and doctor in `src/spec_ops/rescue/doctor.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary python files assert that `spec-ops check --fast` evaluates line length limits and AST bounded-context import boundaries in under 50ms without raising unhandled exceptions or reporting false positives on compliant code.
- **Mutmut Mutation Scope**: Fast check evaluation in `src/spec_ops/rescue/fast_check.py` and step caching in `src/spec_ops/rescue/incremental_runner.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops check --fast --file <path> --format json` runs in under 50ms, outputs JSON diagnostic warnings at >=400 lines and hard errors at >=500 lines with line numbers, and detects unauthorized cross-bounded-context imports.
2. Inside a rescued worktree, executing `spec-ops rescue test --only-failed` reruns only the previously failed preflight step in under 3 seconds, while `spec-ops rescue <task-id> --complete` bypasses caches and runs the full suite.
3. Executing `spec-ops task create --title <t> --bc <bc> --prd <prd> --story <us>` scaffolds a valid proposed task file and updates `PRIORITY.md`; promoting via `spec-ops queue refine` blocks if DoR is unsatisfied.
4. Executing `spec-ops visualizer --serve --entity TASK-XXXX` opens the browser to `#entity=TASK-XXXX` highlighting upstream stories, downstream dependents, and bounded context pills.
5. Executing `spec-ops docs check` audits public CLI commands against `docs/how-to/` and `docs/reference/` and flags undocumented commands with non-zero exit code.
6. Executing `spec-ops doctor` audits UV workspace, worktrees gitignore, pre-commit hooks, and line limit health; passing `--fix` installs missing hooks and auto-configures the environment.
7. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
