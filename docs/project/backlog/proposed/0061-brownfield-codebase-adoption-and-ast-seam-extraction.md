---
id: '0061'
title: Brownfield Codebase Adoption, Grandfathered File Debt Baseline, and AST Seam Extraction
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0060
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
  - US-0011
  - US-0013
  - US-0015
target_bc: core
---

# TASK-0061: Brownfield Codebase Adoption, Grandfathered File Debt Baseline, and AST Seam Extraction

## Summary
Implement tools for brownfield repository adoption and structural anti-rot governance: grandfathered file debt baselining (`spec-ops adopt [--grandfather-debt]`), proactive AST seam analysis with modular decomposition recommendations (`spec-ops decompose --suggest <file>`), automatic generation of backlog refactoring tasks for grandfathered oversized files (`spec-ops health --generate-refactor-tasks`), and static bounded context import boundary enforcement (`spec-ops health --architecture`).

## Problem Statement & Context
Introducing SpecOps into mature, brownfield repositories often encounters hundreds of existing source files that violate file length limits (<500 lines) or lack bounded context isolation. Enforcing hard invariants immediately without a transition path causes preflight checks to fail universally, halting adoption. Conversely, failing to enforce boundaries allows rot to compound. SpecOps requires a grandfathering baseline mechanism that isolates legacy debt, strictly gates newly authored files, automatically generates backlog refactoring tasks, suggests AST decomposition seams, and validates DDD architecture boundaries.

## User Stories & Scenarios Satisfied
- **US-0011: Brownfield Codebase Adoption and Anti-Rot Invariant Baseline**
  - *Scenario: Initializing SpecOps in an existing repository with grandfathered file debt*
  - *Scenario: Enforcing anti-rot invariant against newly created files while respecting grandfathered files*
  - *Scenario: Automatically generating proposed refactoring tasks for grandfathered files*
- **US-0013: Bounded Context Boundary and Dependency Direction Enforcement**
  - *Scenario: Clean repository verifying bounded context isolation*
  - *Scenario: Catching illegal cross-context domain import in CI*
  - *Scenario: Detecting circular bounded context dependencies*
- **US-0015: Proactive File Decomposition Suggestions and AST Seam Extraction**
  - *Scenario: Generating decomposition suggestions for files in the warning threshold (400-500 lines)*
  - *Scenario: Emitting a proposed refactoring task into the backlog*
  - *Scenario: Preserving clean status when all files remain under 400 lines*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Baseline debt tracker in `src/spec_ops/core/debt_baseline.py`, AST seam extractor in `src/spec_ops/core/ast_seams.py`, and architecture boundary checker in `src/spec_ops/core/arch_checker.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that `spec-ops health` never rejects a repository if all exceeding files are registered in `.specops/grandfathered_debt.json` and unchanged, but immediately rejects any modification that increases line count of a grandfathered file.
- **Mutmut Mutation Scope**: Boundary import parsing in `src/spec_ops/core/arch_checker.py` and seam recommendation heuristics in `src/spec_ops/core/ast_seams.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops adopt --grandfather-debt` scans an existing codebase, registers oversized files into `.specops/grandfathered_debt.json` with baseline line counts, and allows `spec-ops health` to exit with code 0.
2. Introducing a new file >500 lines or expanding an existing grandfathered file beyond its recorded baseline triggers an immediate exit code 1 in `spec-ops health`.
3. Executing `spec-ops decompose --suggest <path>` analyzes Python and TypeScript ASTs and outputs candidate cohesive class/function groupings for decomposition.
4. Executing `spec-ops health --generate-refactor-tasks` emits structured proposed tasks in `docs/project/backlog/proposed/` targeting grandfathered files with suggested AST seams.
5. Executing `spec-ops health --architecture` parses import trees against `specops.toml` bounded context rules and catches illegal cross-context imports (e.g. domain importing external infrastructure) or cyclic package imports with exit code 1.
6. All acceptance criteria verified via public frontdoor `pytest-bdd` tests without mock backdoors (ADR-0003, ADR-0006).
