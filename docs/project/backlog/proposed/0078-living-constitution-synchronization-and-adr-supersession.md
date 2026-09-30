---
id: '0078'
title: Living Constitution Synchronization, ADR Supersession, and CI Drift Gate
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0010
  - TASK-0063
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0007
  - ADR-0008
governing_prds:
  - PRD-0005
governing_stories:
  - US-0014
  - US-0068
target_bc: scaffold
---

# TASK-0078: Living Constitution Synchronization, ADR Supersession, and CI Drift Gate

## Summary
Implement automated ADR supersession workflow (`spec-ops adr supersede <old-id> --by <new-id>`), living constitution synchronization (`spec-ops constitution sync`), extension-preserving scaffolding that protects human-authored custom rules in `AGENTS.md`, and a fast-fail CI constitution drift gate (`spec-ops constitution check`) that alerts when configuration or ADR updates have not been synchronized into active agent operating rules.

## Problem Statement & Context
When architecture evolves, ADRs are superseded and repository invariants change in `specops.toml`. If `AGENTS.md` is not updated atomically, autonomous coding agents continue operating under obsolete constraints, writing code that fails preflight checks. Conversely, naively regenerating `AGENTS.md` wipes out custom project instructions authored by human developers. SpecOps requires a dedicated constitution synchronizer that tracks ADR supersession, flags active tasks citing obsolete decisions, preserves custom human sections, and verifies synchronization in CI.

## User Stories & Scenarios Satisfied
- **US-0014: Architectural Decision Record Supersession and Living Constitution Synchronization**
  - *Scenario: Superseding an ADR and updating registry links*
    - Given an active ADR-0004 in "docs/project/adrs/accepted/"
    - When the architect runs "spec-ops adr supersede ADR-0004 --by ADR-0014"
    - Then ADR-0004 status is updated to "Superseded", ADR-0014 links are cross-referenced, and "REGISTRY.md" is updated.
  - *Scenario: Re-synchronizing AGENTS.md constitution upon ADR supersession*
    - Given a superseded ADR cited in "AGENTS.md"
    - When "spec-ops constitution sync" is executed
    - Then the Invariants section of "AGENTS.md" is rewritten to reflect the new governing ADR.
  - *Scenario: Flagging active backlog tasks citing superseded ADRs*
    - Given a refined task in "docs/project/backlog/refined/" citing ADR-0004
    - When "spec-ops constitution check" is run
    - Then a warning is reported that active tasks cite superseded ADRs.
- **US-0068: Living Constitution Synchronization, Extension Preservation, and CI Drift Gate**
  - *Scenario: Re-synchronizing constitution when specops.toml settings change*
    - Given an updated file limit in "specops.toml"
    - When "spec-ops constitution sync" runs
    - Then "AGENTS.md" is synchronized with the new limit.
  - *Scenario: Preserving human-authored custom invariant extensions across sync*
    - Given custom developer directives inside a "<!-- CUSTOM_RULES_START -->" comment block in "AGENTS.md"
    - When "spec-ops constitution sync" regenerates the document
    - Then all custom instructions within the boundary block are preserved intact.
  - *Scenario: CI constitution drift detection gate*
    - Given an out-of-sync "AGENTS.md"
    - When "spec-ops constitution check" is run in CI
    - Then the process exits with code 1 and outputs the exact discrepancy.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Constitution synchronizer in `src/spec_ops/scaffold/constitution_sync.py` and ADR supersession handler in `src/spec_ops/adrs/supersede.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that arbitrary text enclosed within custom rule boundary blocks is preserved verbatim across repeated constitution synchronization passes (idempotent preservation invariant).
- **Mutmut Mutation Scope**: Custom section preservation logic in `src/spec_ops/scaffold/constitution_sync.py` achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops adr supersede` atomically updates frontmatter, registry, and cross-references.
2. Executing `spec-ops constitution sync` regenerates `AGENTS.md` while preserving custom blocks byte-for-byte.
3. Executing `spec-ops constitution check` exits 0 on synchronized state or 1 with diff on drift.
4. Active tasks citing superseded ADRs surfaced proactively during validation.
5. All scenarios executed via `pytest-bdd` against CLI frontdoors with zero mock backdoors (ADR-0003, ADR-0006).
