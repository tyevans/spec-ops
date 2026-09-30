---
id: '0077'
title: Architectural Profile Version Lifecycle, Semantic Diffs, and Invariant Migrations
status: Complete
dependencies:
- TASK-0063
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
- ADR-0008
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0070
target_bc: scaffold
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0077: Architectural Profile Version Lifecycle, Semantic Diffs, and Invariant Migrations

## Summary
Implement profile version upgrading and semantic invariant diffing (`spec-ops profile diff [profile]`, `spec-ops profile upgrade [profile]`). Enable engineering leads to preview upstream architectural changes, detect tightening or loosening of invariant limits, inspect baseline ADR additions or deprecations, and perform safe three-way migrations of modified local ADRs with rollback capabilities.

## Problem Statement & Context
When baseline architectural profiles evolve (e.g. adopting stricter file size thresholds or introducing new security gates), engineering teams need to upgrade their local repository constitutions without unintentionally clobbering local modifications or manually sifting through raw git diffs. SpecOps requires semantic diffing and automated migration tooling tailored specifically to architectural profiles and baseline ADRs.

## User Stories & Scenarios Satisfied
- **US-0070: Architectural Profile Version Lifecycle, Semantic Diffs, and Invariant Migrations**
  - *Scenario: Inspecting profile upgrades and semantic invariant diffs*
    - Given a repository using "specops/base@v1.0"
    - When the architect runs "spec-ops profile diff specops/base@v2.0"
    - Then the system outputs a semantic diff highlighting new ADRs, updated file limits, and deprecations.
  - *Scenario: Applying profile upgrade and migrating baseline ADRs*
    - Given an available profile upgrade
    - When the architect runs "spec-ops profile upgrade"
    - Then upstream ADR additions and non-conflicting amendments are applied cleanly and the lockfile is updated.
  - *Scenario: Safe migration abort on conflicting local ADR modifications*
    - Given local edits to an ADR that was also modified upstream
    - When the architect runs "spec-ops profile upgrade"
    - Then the system pauses, displays the 3-way conflict, and provides a safe abort/resolve prompt without corrupting files.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Profile migration engine in `src/spec_ops/profiles/migration.py` and semantic diff calculator in `src/spec_ops/profiles/diff.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that profile diff calculation is commutative with respect to invariant ordering and abort cleanly preserves repository state verbatim.
- **Mutmut Mutation Scope**: Semantic diff evaluation in `src/spec_ops/profiles/diff.py` achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops profile diff` outputs human-readable and machine-readable semantic diffs of profile invariant changes.
2. Executing `spec-ops profile upgrade` updates profile dependencies and applies baseline ADR updates cleanly.
3. Conflicting local ADR edits trigger safe abort mechanisms without state corruption.
4. All acceptance criteria verified via public CLI frontdoors with `pytest-bdd` (ADR-0003, ADR-0006).
