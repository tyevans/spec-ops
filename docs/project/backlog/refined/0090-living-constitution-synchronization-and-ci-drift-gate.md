---
id: 0090
title: Living Constitution Synchronization, Extension Preservation, and CI Drift Gate
status: Refined
dependencies:
- TASK-0078
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
- US-0068
target_bc: scaffold
claimed_by: worker-3
branch: feat/0090-living-constitution-synchronization--ext
---

# TASK-0090: Living Constitution Synchronization, Extension Preservation, and CI Drift Gate

## Summary
Implement living constitution synchronization (`spec-ops constitution sync`), delimiter-boundary preservation of human-authored instructions in `AGENTS.md`, and a fast-fail CI drift detection gate (`spec-ops constitution check`) to ensure autonomous agents and human developers operate under current architectural laws without overwriting local custom rules.

## Problem Statement & Context
When architecture evolves, repository invariants change in `specops.toml` or baseline profiles. If `AGENTS.md` is not updated atomically, autonomous coding agents operate under obsolete constraints and fail preflight checks. However, naive re-scaffolding wipes out custom operational guidelines authored by human developers. SpecOps requires constitution synchronization that preserves marked human custom sections verbatim and enforces synchronization in CI.

## User Stories & Scenarios Satisfied
- **US-0068: Living Constitution Synchronization, Extension Preservation, and CI Drift Gate**
  - *Scenario: Re-synchronizing constitution when specops.toml settings change*
  - *Scenario: Preserving human-authored custom invariant extensions across sync*
  - *Scenario: CI constitution drift detection gate*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Constitution synchronizer in `src/spec_ops/scaffold/constitution_sync.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that arbitrary text enclosed within `<!-- BEGIN CUSTOM INVARIANTS -->` and `<!-- END CUSTOM INVARIANTS -->` comment blocks is preserved verbatim across repeated constitution synchronization passes.
- **Mutmut Mutation Scope**: Boundary parsing and preservation logic in `src/spec_ops/scaffold/constitution_sync.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops constitution sync` regenerates `AGENTS.md` and `docs/operating-manual.md` from `specops.toml` settings while preserving marked custom sections intact.
2. Executing `spec-ops constitution check` exits 0 when `AGENTS.md` is synchronized with configuration and exits 1 with actionable diff diagnostics when out-of-sync.
3. All scenarios executed via `pytest-bdd` against CLI frontdoors with zero mock backdoors (ADR-0003, ADR-0006).
