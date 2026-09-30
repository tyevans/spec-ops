---
id: 0085
title: Bounded-Context Diataxis Documentation Scaffolding and Living Spec Linking
status: Complete
dependencies:
- TASK-0064
- TASK-0015
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0007
- ADR-0008
governing_prds:
- PRD-0005
governing_stories:
- US-0071
target_bc: scaffold
---

# TASK-0085: Bounded-Context Diataxis Documentation Scaffolding and Living Spec Linking

## Summary
Implement automated bounded-context documentation scaffolding (`spec-ops scaffold docs --bc <name> [--title <title>]`). Generate compliant Diataxis quadrants (`tutorials/`, `how-to/`, `reference/`, and `explanation/`) populated with boilerplate templates, architectural context, and bidirectional permalinks to the living 2D visualizer graph canvas.

## Problem Statement & Context
As new bounded contexts are introduced in evolving domain models, engineering teams often fail to author consistent Diataxis documentation structures or link them to existing specifications. This leads to documentation drift and isolated documentation silos. SpecOps requires a dedicated scaffolding command that creates properly segmented Diataxis directories for any bounded context with pre-configured cross-references and visualizer deep links.

## User Stories & Scenarios Satisfied
- **US-0071: Bounded-Context Diataxis Documentation Scaffolding and Living Spec Linking**
  - *Scenario: Scaffolding Diataxis quadrant for a new bounded context*
    - Given an active SpecOps repository with bounded contexts
    - When the developer executes "spec-ops scaffold docs --bc billing --title 'Billing Subsystem'"
    - Then documentation directories are created with boilerplate index files across all four Diataxis quadrants.
  - *Scenario: Embedding deep links to the living 2D visualizer*
    - Given scaffolded bounded-context documentation
    - When viewing the generated reference documents
    - Then markdown files include URL hash deep links targeting the bounded context in the 2D visualizer.
  - *Scenario: Preventing duplicate bounded context scaffolding*
    - Given an existing bounded context documentation tree
    - When attempting to scaffold the same bounded context without "--force"
    - Then the command warns the user and preserves existing documentation intact.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Documentation scaffolding logic in `src/spec_ops/scaffold/docs_scaffold.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary bounded context identifier strings assert that generated paths conform strictly to Diataxis directory invariants and contain no invalid path traversal characters.
- **Mutmut Mutation Scope**: Markdown template interpolation and permalink generation in `src/spec_ops/scaffold/docs_scaffold.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops scaffold docs --bc <name>` creates `docs/tutorials/<name>/`, `docs/how-to/<name>/`, `docs/reference/<name>/`, and `docs/explanation/<name>/`.
2. Each generated document contains valid frontmatter and visualizer deep-link anchors.
3. Running `spec-ops docs audit` immediately following scaffolding reports 0 errors and 0 warnings.
4. Attempting to overwrite existing documentation without `--force` exits cleanly with code 1 without file corruption.
5. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
