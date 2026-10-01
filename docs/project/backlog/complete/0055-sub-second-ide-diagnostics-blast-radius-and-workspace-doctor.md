---
id: '0055'
title: Sub-Second IDE Invariant Diagnostics and Real-Time Editor Feedback
status: Complete
dependencies:
- TASK-0013
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
target_bc: rescue
---

# TASK-0055: Sub-Second IDE Invariant Diagnostics and Real-Time Editor Feedback

## Summary
Deliver rapid developer ergonomics and sub-second editor tooling: implement sub-50ms single-file invariant diagnostic checks (`spec-ops check --fast --file <path> [--format json|sarif]`) for real-time IDE linting, surfacing file length violations (>=400 warning, >=500 error) and illegal cross-bounded-context imports directly on file-save.

## Problem Statement & Context
Human developers working alongside autonomous agents require rapid local iteration loops without waiting for slow preflight suites. Line length and bounded context import violations must be surfaced in real time in IDEs on file-save rather than at pre-commit or CI time. Surfacing diagnostics in <50ms enables seamless language server protocol (LSP) and editor integration.

## User Stories & Scenarios Satisfied
- **US-0091: Sub-Second Incremental Invariant Diagnostics for Editor and IDE Feedback**
  - *Scenario: Blazing fast single-file invariant evaluation on save*
    - Given a developer editing a Python file in an IDE
    - When "spec-ops check --fast --file <path>" executes upon file save
    - Then execution completes in under 50ms and reports clean status.
  - *Scenario: Immediate diagnostic error on hard invariant violation*
    - Given a source file edited beyond 500 lines
    - When the fast check runs
    - Then an exit code 1 is returned with JSON diagnostic pointing to the exact line threshold.
  - *Scenario: Bounded context boundary import validation*
    - Given an unauthorized import across bounded context boundaries
    - When the fast check runs
    - Then a diagnostic violation citing ADR-0007 is returned with file and column pointers.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Diagnostic evaluator in `src/spec_ops/rescue/fast_check.py` stays strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary python files assert that `spec-ops check --fast` evaluates line length limits and AST bounded-context import boundaries in under 50ms without raising unhandled exceptions or reporting false positives on compliant code.
- **Mutmut Mutation Scope**: Fast check evaluation in `src/spec_ops/rescue/fast_check.py` achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops check --fast --file <path> --format json` runs in under 50ms, outputs JSON diagnostic warnings at >=400 lines and hard errors at >=500 lines with line numbers, and detects unauthorized cross-bounded-context imports.
2. Formats supported include human-readable text, JSON, and SARIF for GitHub / IDE integration.
3. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
