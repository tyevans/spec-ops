---
id: '0063'
title: Modular Architectural Profile Inheritance, Semantic Invariant Diffs, and Living Constitution Lifecycle
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0063
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
  - US-0070
  - US-0014
  - US-0068
target_bc: scaffold
---

# TASK-0064: Modular Architectural Profile Inheritance, Semantic Invariant Diffs, and Living Constitution Lifecycle

## Summary
Implement hierarchical profile composition and inheritance (`extends = ["base", "security"]`), custom profile packaging and multi-repo distribution (`spec-ops profile export/install`), profile version upgrading with semantic diffing (`spec-ops profile diff`, `spec-ops profile upgrade`), automated ADR supersession with registry and AGENTS.md re-synchronization (`spec-ops adr supersede`), and a CI living constitution drift gate (`spec-ops constitution check`) that preserves human-authored custom extensions across syncs.

## Problem Statement & Context
Engineering organizations manage multiple repositories sharing core architectural standards (e.g. security postures, testing conventions, and file limits) while requiring local specialized overrides. Without composable profile inheritance, profiles duplicate boilerplate and diverge across projects. When baseline ADRs or profiles are updated upstream, repositories suffer from unguided drift or conflicting migrations. Additionally, updating ADRs or profile invariants without automatically syncing `AGENTS.md` leaves AI coding agents operating under stale constitutions. SpecOps needs composable profile inheritance and automated constitution lifecycle tooling.

## User Stories & Scenarios Satisfied
- **US-0012: Custom Architectural Profile Authoring and Multi-Repo Distribution**
  - *Scenario: Packaging a custom organizational profile*
  - *Scenario: Initializing a project using an exported custom profile bundle*
  - *Scenario: Detecting conflicting or duplicate ADR numbers in composite profiles*
- **US-0067: Hierarchical Profile Inheritance, Composition, and Invariant Overrides**
  - *Scenario: Defining a custom profile inheriting from parent profiles*
  - *Scenario: Overriding specific invariant thresholds in a derived profile*
  - *Scenario: Detecting circular inheritance and conflicting invariant overrides*
- **US-0070: Architectural Profile Version Lifecycle, Semantic Diffs, and Invariant Migrations**
  - *Scenario: Inspecting profile upgrades and semantic invariant diffs*
  - *Scenario: Applying profile upgrade and migrating baseline ADRs*
  - *Scenario: Safe migration abort on conflicting local ADR modifications*
- **US-0014: Architectural Decision Record Supersession and Living Constitution Synchronization**
  - *Scenario: Superseding an ADR and updating registry links*
  - *Scenario: Re-synchronizing AGENTS.md constitution upon ADR supersession*
  - *Scenario: Flagging active backlog tasks citing superseded ADRs*
- **US-0068: Living Constitution Synchronization, Extension Preservation, and CI Drift Gate**
  - *Scenario: Re-synchronizing constitution when specops.toml settings change*
  - *Scenario: Preserving human-authored custom invariant extensions across sync*
  - *Scenario: CI constitution drift detection gate*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Profile composer in `src/spec_ops/profiles/composer.py`, profile migration engine in `src/spec_ops/profiles/migration.py`, and constitution synchronizer in `src/spec_ops/scaffold/constitution_sync.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary DAGs of inherited profile manifests assert that composite invariant evaluation resolves deterministically without order-dependent side effects, and cyclic inheritance graphs are rejected with informative errors.
- **Mutmut Mutation Scope**: Profile override resolution in `src/spec_ops/profiles/composer.py` and semantic diff evaluation in `src/spec_ops/profiles/migration.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops profile export <profile-name> --output bundle.tar.gz` packages custom ADRs, constitution rules, and configuration for multi-repo distribution.
2. Specifying multiple parent profiles in `specops.toml` resolves inheritance hierarchy, allowing leaf profiles to override specific invariant thresholds (e.g. `file_length_limit = 450`) and detecting circular inheritance loops with exit code 1.
3. Executing `spec-ops profile diff <upstream-profile>` outputs a colorized semantic diff of changed invariants, added ADRs, and modified constitution directives.
4. Executing `spec-ops profile upgrade <upstream-profile>` applies updates safely, refusing to overwrite locally modified baseline ADRs without `--force`.
5. Executing `spec-ops adr supersede ADR-XXXX --by ADR-YYYY` updates ADR registry status, updates active task references, and re-synchronizes `AGENTS.md` while preserving human-authored custom extensions.
6. Executing `spec-ops constitution check` in CI verifies that `AGENTS.md` accurately reflects active profile ADRs and exits with code 1 upon detected drift.
7. All acceptance criteria verified via public frontdoor `pytest-bdd` tests without mock backdoors (ADR-0003, ADR-0006).
