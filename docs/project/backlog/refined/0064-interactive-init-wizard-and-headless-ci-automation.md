---
id: '0064'
title: Interactive Guided Initialization Wizard and Headless CI Automation Scaffolding
status: Refined
dependencies:
  - TASK-0063
  - TASK-0012
governing_adrs:
  - ADR-0001
  - ADR-0003
  - ADR-0004
  - ADR-0007
  - ADR-0008
governing_prds:
  - PRD-0005
governing_stories:
  - US-0066
target_bc: scaffold
---

# TASK-0064: Interactive Guided Initialization Wizard and Headless CI Automation Scaffolding

## Summary
Implement an interactive terminal initialization wizard (`spec-ops init --interactive`) featuring live syntax-highlighted configuration previews alongside an unattended headless initialization mode (`spec-ops init --headless --profile <p>`) and dry-run preview (`spec-ops init --dry-run`). Streamline developer and agent onboarding by dynamically prompting for project identity, architectural profile composition, and initial bounded contexts while ensuring zero regressions across non-interactive script environments.

## Problem Statement & Context
Scaffolding a new repository using SpecOps currently requires knowing CLI flags and understanding profile inheritance hierarchies upfront. When engineers or automation scripts initialize a new workspace, invalid combinations or typos result in broken initial configurations. SpecOps requires a rich interactive terminal onboarding wizard for human architects alongside a deterministic, headless non-interactive mode for CI/CD container templates and autonomous setup pipelines.

## User Stories & Scenarios Satisfied
- **US-0066: Interactive Guided Initialization Wizard and Headless CI Automation Scaffolding**
  - *Scenario: Interactive terminal onboarding wizard with live configuration preview*
    - Given a developer runs "spec-ops init --interactive" in an uninitialized directory
    - When they select the "core" and "security" profiles and declare a "billing" bounded context
    - Then the wizard renders a formatted preview of "specops.toml" and scaffolds the repository upon user confirmation.
  - *Scenario: Unattended headless initialization for CI and automation templates*
    - Given an automated CI provisioning pipeline
    - When the container executes "spec-ops init --headless --name PaymentService --profile core"
    - Then the repository is scaffolded non-interactively without stdin blocking in under 2 seconds.
  - *Scenario: Initialization dry-run preview mode*
    - Given a developer testing initialization parameters
    - When they run "spec-ops init --dry-run --profile core,bdd"
    - Then the system prints planned files and generated "specops.toml" without creating files on disk.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Initialization wizard implementation in `src/spec_ops/scaffold/wizard.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomized combinations of project names, profiles, and bounded contexts assert that `spec-ops init --dry-run` and `spec-ops init --headless` generate identical configuration ASTs without side-effects or partial directory pollution upon validation failure.
- **Mutmut Mutation Scope**: Interactive state handling and configuration serialization in `src/spec_ops/scaffold/wizard.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops init --interactive` guides the user through profile selection, bounded context declaration, and configuration preview using Rich prompt helpers.
2. Executing `spec-ops init --headless --profile core` initializes a compliant project non-interactively in under 2 seconds without prompt blocking.
3. Executing `spec-ops init --dry-run` outputs the planned directory tree and serialized `specops.toml` content to stdout with 0 files created on disk.
4. Validation errors (invalid profile name, duplicate bounded context, illegal directory name) abort cleanly with explanatory diagnostics and exit code 1.
5. All scenarios verified via public frontdoor `pytest-bdd` tests (`tests/test_bdd_us0066.py`) without private mock backdoors (ADR-0003, ADR-0006).
