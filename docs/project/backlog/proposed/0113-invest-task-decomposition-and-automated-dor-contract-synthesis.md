---
id: '0113'
title: INVEST Task Decomposition and Automated DoR Contract Synthesis
status: Proposed
dependencies:
  - TASK-0109
  - TASK-0111
  - TASK-0112
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0006
  - ADR-0007
  - ADR-0008
  - ADR-0009
governing_prds:
  - PRD-0006
governing_stories:
  - US-0117
target_bc: backlog
---

# TASK-0113: INVEST Task Decomposition and Automated DoR Contract Synthesis

## Summary
Implement automated task decomposition and Definition of Ready (DoR) contract synthesis (`spec-ops task decompose` and `spec-ops task synthesize-dor`) that parses accepted PRDs and BDD user stories, breaks them into INVEST-compliant thin vertical slices (<500 lines per file) and architectural spikes, and synthesizes executable Gherkin scenarios and Hypothesis generative property invariants directly into task files in `docs/project/backlog/proposed/`.

## Problem Statement & Context
Tasks drafted during initial planning frequently lack concrete acceptance criteria, executable BDD scenarios, or explicit property invariants, leading to high rejection rates during JIT refinement. An orchestrator skill must be able to autonomously synthesize robust DoR contracts from checkable PRD outcomes and existing codebase AST interfaces.

## User Stories & Scenarios Satisfied
- **US-0117: Autonomous Full-Lifecycle SDLC Orchestrator Skill & Multi-Agent Coordination**
  - *Scenario: INVEST Slicing and DoR Synthesis*
    - Given an accepted PRD with multiple checkable outcomes
    - When the orchestrator executes "spec-ops task decompose --prd PRD-XXXX"
    - Then the engine estimates file impact, identifies AST module seams, and slices the scope into vertical tasks <500 lines
    - And generates executable Gherkin scenarios and property test targets for each task.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Task decomposition module in `src/spec_ops/backlog/invest_decomposer.py` must stay strictly under 400 lines (ADR-0002).
- **INVEST Compliance**: Every generated task must be scoped to a single bounded context and estimated under 400 lines of implementation diff.
- **Mutmut Mutation Scope**: AST seam decomposition heuristics achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. CLI commands `spec-ops task decompose` and `spec-ops task synthesize-dor` implemented.
2. Generates tasks in `docs/project/backlog/proposed/` satisfying all Definition of Ready (DoR) criteria.
3. Automatically identifies and scaffolds architectural spikes (`SPIKE-XXXX`) when architectural uncertainty is detected.
4. 100% test pass rate verifying observable contracts without private mock backdoors.
