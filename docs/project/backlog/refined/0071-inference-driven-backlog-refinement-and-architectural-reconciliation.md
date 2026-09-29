---
id: '0071'
title: Inference-Driven Backlog Refinement, Architectural Drift Reconciliation, and Scope Slicing
status: Refined
priority: High
dependencies:
  - TASK-0007
  - TASK-0004
  - TASK-0014
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0004
  - ADR-0006
  - ADR-0007
  - ADR-0009
governing_prds:
  - PRD-0005
  - PRD-0001
governing_stories:
  - US-0116
target_bc: backlog
---

# TASK-0071: Inference-Driven Backlog Refinement, Architectural Drift Reconciliation, and Scope Slicing

## Summary
Implement cognitive, inference-driven backlog curation (`spec-ops curate --infer` and upgraded `/curate` agent skill): transform curation from a naive file-moving utility into an intelligent refinement engine that evaluates proposed tasks against living codebase reality, reconciles architectural drift across superseded ADRs and refactored modules, autonomously decomposes oversized tasks (>500 lines) into INVEST-compliant thin vertical slices and spikes, and generatively synthesizes missing Definition of Ready (DoR) acceptance criteria (executable Gherkin scenarios and Hypothesis property invariants) instead of passively rejecting work.

## Problem Statement & Context
Tasks authored during initial PRD decomposition often sit in `proposed/` for weeks before entering the active ready buffer. During that latency window, repository reality moves rapidly: architectural decisions (ADRs) are superseded, modules are decomposed or renamed, and APIs evolve. The current curation command (`spec-ops curate`) acts as a dumb file-moving utility (`mv proposed/TASK.md refined/TASK.md`), blindly promoting tasks with obsolete assumptions, bloated scopes doomed to violate the 500-line modular limit (ADR-0002), or missing executable acceptance criteria. Furthermore, the Antigravity `/curate` slash command merely executes this basic script, wasting host LLM reasoning. SpecOps requires an inference-driven curation engine and an interactive agent refinement skill that reconcile architectural drift and synthesize actionable contracts prior to promotion.

## User Stories & Scenarios Satisfied
- **US-0116: Inference-Driven Backlog Refinement, Architectural Drift Reconciliation, and Scope Slicing**
  - *Scenario: Detecting Architectural Drift and Reconciling Stale Task Specifications*
  - *Scenario: Autonomously Slicing Oversized Monolithic Tasks into Thin Vertical Slices*
  - *Scenario: Generative Definition of Ready (DoR) Synthesis instead of Dumb Rejection*
  - *Scenario: Interactive AI-Native /curate Slash Command Skill*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Inference curator in `src/spec_ops/backlog/inference_curator.py`, autonomous task slicer in `src/spec_ops/backlog/slicer.py`, and architectural reconciler in `src/spec_ops/backlog/reconciler.py` must stay strictly under 400 lines (ADR-0002).
- **Blackbox Frontdoor Verification (ADR-0003)**: All functionality exercised through public CLI flags (`spec-ops curate --infer [--dry-run] [--model <name>]`) and domain orchestrators without private backdoor state manipulation.
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly generated task structures and dependency graphs assert:
  1. *Decomposition Completeness*: Slicing an oversized task preserves 100% of governing PRD checkable outcomes and tags across child slices without dropped scope.
  2. *Sequential Dependency & ID Invariant*: Synthesized child slice IDs are strictly unique, sequential, and non-colliding. Prerequisite spike tasks strictly precede implementation slices in `PRIORITY.md`.
  3. *Size Invariant*: Decomposed child slices restrict estimated scope strictly beneath modular boundaries (<400 lines).
- **Mutmut Mutation Scope**: Core slicing logic in `src/spec_ops/backlog/slicer.py` and reconciliation diff evaluation in `src/spec_ops/backlog/reconciler.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops curate --infer --dry-run` audits candidate tasks in `proposed/` against current AST nodes, active ADRs in `docs/project/adrs/accepted/`, and existing bounded contexts, outputting an inspection diff of proposed reconciliations without modifying disk state.
2. Executing `spec-ops curate --infer` automatically updates stale file paths, superseded ADR citations, and bounded context references in candidate tasks before promotion to `docs/project/backlog/refined/`.
3. When candidate tasks lack executable Gherkin scenarios, `spec-ops curate --infer` inspects the governing PRD `## Checkable Outcomes` and synthesizes valid `Given ... When ... Then` acceptance criteria satisfying the Definition of Ready (DoR).
4. When a proposed task touches multiple bounded contexts or exceeds estimated single-file line thresholds, the engine decomposes it into discrete sequential vertical slices (and an exploratory spike if architectural uncertainty is detected), placing child tasks in `proposed/` and promoting only the first slice to `refined/`.
5. The Antigravity `/curate` slash command skill is updated to provide an interactive multi-agent refinement workflow that reviews proposed candidates, shows architectural diffs, and prompts the user/agent before promoting tasks.
6. All acceptance criteria verified via public frontdoor `pytest-bdd` tests without mock backdoors (ADR-0003, ADR-0006).

---
