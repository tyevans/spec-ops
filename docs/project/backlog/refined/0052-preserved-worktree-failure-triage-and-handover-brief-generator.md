---
id: '0052'
title: Interactive Preserved Worktree Failure Triage and Diagnostic Takeover
status: Refined
dependencies:
- TASK-0047
- TASK-0051
governing_adrs:
- ADR-0002
- ADR-0003
- ADR-0004
- ADR-0005
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0004
governing_stories:
- US-0087
- US-0035
target_bc: rescue
claimed_by: worker-3
branch: feat/0052-interactive-preserved-worktree-failure-t
---

# TASK-0052: Interactive Preserved Worktree Failure Triage and Diagnostic Takeover

## Summary
Implement interactive failure triage (`spec-ops rescue triage <task-id>`) with categorized root-cause breakdowns, AST diff inspection, and diagnostic human takeover (`spec-ops rescue takeover <task-id>`) allowing developers to seamlessly resume work in a preserved agent worktree.

## Problem Statement & Context
When an autonomous agent fails or stalls, human engineers need fast diagnostic breakdown showing why the agent failed (preflight test error, file length limit violation, AST syntax defect) without having to manually read hundreds of lines of raw logs. SpecOps requires a dedicated rescue triage command and seamless takeover workflow to allow developers to inspect and complete the work.

## User Stories & Scenarios Satisfied
- **US-0087: Interactive Preserved Worktree Triage and Failure Diagnostic Breakdown**
  - *Scenario: Categorizing preflight failure modes in a stalled worktree*
    - Given a preserved worktree where preflight failed
    - When "spec-ops rescue triage <task-id>" runs
    - Then failures are categorized by type (test failure, file length, syntax error) with line pointers.
  - *Scenario: Inspecting AST and line count diffs per modified file*
    - Given modified source files in the worktree
    - When triage is executed
    - Then line count deltas and AST structural diffs are displayed.
- **US-0035: Stalled Autonomous Worktree Inspection and Diagnostic Takeover**
  - *Scenario: Inspecting a stalled agent worktree with diagnostics*
    - Given a preserved worktree in `.worktrees/`
    - When the developer executes "spec-ops rescue inspect <task-id>"
    - Then branch name, last commit, test output, and file diffs are shown.
  - *Scenario: Human takeover, verification, and atomic merge into main*
    - Given an inspected worktree
    - When the developer executes "spec-ops rescue takeover <task-id>"
    - Then the task claim is transferred to the human developer and instructions are printed.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Rescue triage and takeover handlers in `src/spec_ops/rescue/triage.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that `spec-ops rescue triage` correctly classifies arbitrary log strings into the recognized failure taxonomy.
- **Mutmut Mutation Scope**: Log parsing, classification, and diff calculation in `src/spec_ops/rescue/triage.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops rescue triage <task-id>` parses failure logs and prints categorized diagnostics with line numbers.
2. Executing `spec-ops rescue takeover <task-id>` transitions claim to human developer and provisions the worktree for human editing.
3. All scenarios verified via public frontdoor `pytest-bdd` tests without mock backdoors (ADR-0003, ADR-0006).
