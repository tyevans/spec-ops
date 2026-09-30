---
id: '0063'
title: Modular Architectural Profile Inheritance and Composition Engine
status: Complete
dependencies:
- TASK-0062
- TASK-0010
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
- ADR-0008
governing_prds:
- PRD-0005
governing_stories:
- US-0012
- US-0067
target_bc: scaffold
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0063: Modular Architectural Profile Inheritance and Composition Engine

## Summary
Implement hierarchical profile composition and inheritance (`extends = ["base", "security"]`) and custom profile packaging and multi-repo distribution (`spec-ops profile export <name> --output bundle.tar.gz`, `spec-ops profile install <bundle>`). Support overriding specific invariant thresholds in derived profiles, reject circular inheritance graphs with clear diagnostic errors, and prevent duplicate or conflicting baseline ADR numbers during composite profile assembly.

## Problem Statement & Context
Engineering organizations manage multiple repositories sharing core architectural standards (e.g. security postures, testing conventions, and file limits) while requiring local specialized overrides. Without composable profile inheritance, profiles duplicate boilerplate and diverge across projects. SpecOps needs composable profile inheritance and distribution tooling to enable standardized architecture as code across organizational repositories.

## User Stories & Scenarios Satisfied
- **US-0012: Custom Architectural Profile Authoring and Multi-Repo Distribution**
  - *Scenario: Packaging a custom organizational profile*
    - Given a repository with customized architectural profiles and baseline ADRs
    - When the architect runs "spec-ops profile export fintech --output dist/fintech-profile.tar.gz"
    - Then a self-contained profile bundle is generated containing all profile manifests, ADR templates, and invariant rules.
  - *Scenario: Initializing a project using an exported custom profile bundle*
    - Given a target empty directory and an exported profile bundle
    - When the developer runs "spec-ops init --profile dist/fintech-profile.tar.gz"
    - Then the project is scaffolded using the custom profile's ADRs and invariants.
  - *Scenario: Detecting conflicting or duplicate ADR numbers in composite profiles*
    - Given two profiles claiming "ADR-0004" with conflicting titles
    - When the architect attempts to compose or install the profiles together
    - Then the system aborts with a collision error and suggests next available ADR numbering.
- **US-0067: Hierarchical Profile Inheritance, Composition, and Invariant Overrides**
  - *Scenario: Defining a custom profile inheriting from parent profiles*
    - Given a profile definition declaring "extends = ['base', 'security']"
    - When "spec-ops profile inspect" is executed
    - Then the resolved profile aggregates the union of baseline ADRs and constraints from both parents.
  - *Scenario: Overriding specific invariant thresholds in a derived profile*
    - Given a derived profile setting "file_length_limit = 350" overriding parent's "500"
    - When invariants are evaluated
    - Then the stricter derived threshold is enforced.
  - *Scenario: Detecting circular inheritance and conflicting invariant overrides*
    - Given a profile cycle "A -> B -> A"
    - When "spec-ops profile inspect" is run
    - Then the CLI reports a circular inheritance error and exits with code 1.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Profile composer in `src/spec_ops/profiles/composer.py` and profile packager in `src/spec_ops/profiles/packager.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary DAGs of inherited profile manifests assert that composite invariant evaluation resolves deterministically without order-dependent side effects, and cyclic inheritance graphs are rejected with informative errors.
- **Mutmut Mutation Scope**: Profile override resolution in `src/spec_ops/profiles/composer.py` achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops profile export` packages valid self-contained profile bundles.
2. Executing `spec-ops init --profile <bundle>` bootstraps repositories with custom profile rules.
3. Hierarchical composition with `extends = [...]` resolves merged ADRs and invariant overrides.
4. Circular profile inheritance detected and rejected with informative error messages.
5. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
