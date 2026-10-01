---
id: '0112'
title: Continuous Product Discovery and Living PRD Synthesis Workflow
status: Refined
dependencies:
- TASK-0109
- TASK-0110
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
- ADR-0008
governing_prds:
- PRD-0006
governing_stories:
- US-0117
target_bc: prd
---

# TASK-0112: Continuous Product Discovery and Living PRD Synthesis Workflow

## Summary
Implement an autonomous product discovery and PRD synthesis workflow (`spec-ops prd discover` and `spec-ops prd shape`) that guides autonomous subagents and human product managers through shaping ideas from `docs/project/product/idea/` into `shaped/` and `accepted/`. Integrates falsifiable PRD linting gates, checkable business outcome extraction, and stakeholder validation.

## Problem Statement & Context
While SpecOps has PRD linting commands (`spec-ops prd lint`), the workflow for taking loose user problems and shaping them into accepted, falsifiable PRDs remains manual and disconnected from the autonomous agent toolchain. An orchestrator skill requires an automated discovery workflow that synthesizes problem statements, defines what good looks like, and validates checkable outcomes.

## User Stories & Scenarios Satisfied
- **US-0117: Autonomous Full-Lifecycle SDLC Orchestrator Skill & Multi-Agent Coordination**
  - *Scenario: Autonomous PRD Discovery and Lifecycle Advancement*
    - Given a raw idea in "docs/project/product/idea/"
    - When the orchestrator executes "spec-ops prd shape --id PRD-XXXX"
    - Then the engine analyzes persona pain points and bounded context boundaries
    - And prompts or generates checkable outcomes and non-goals
    - And moves the PRD to "shaped/" or "accepted/" once lint checks pass.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: PRD discovery module in `src/spec_ops/prd/discovery_workflow.py` must stay strictly under 400 lines (ADR-0002).
- **Checkable Outcome Invariant**: All synthesized PRDs must contain at least 3 falsifiable, automated checkable outcomes.
- **Mutmut Mutation Scope**: PRD lifecycle stage advancement and frontmatter validation achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. CLI commands `spec-ops prd discover` and `spec-ops prd shape` guide idea progression.
2. Enforces mandatory sections and checkable outcomes before allowing transition to `accepted/`.
3. Updates `docs/project/product/REGISTRY.md` automatically.
4. 100% test pass rate verifying observable contracts without private mock backdoors.

## Acceptance Criteria

### Scenario 1: Autonomous PRD Discovery and Lifecycle Advancement*
```gherkin
Given the system is initialized and ready
When the user executes the workflow for "Continuous Product Discovery and Living PRD Synthesis Workflow"
Then Autonomous PRD Discovery and Lifecycle Advancement*
And observable outputs satisfy public contracts without backdoor tampering.
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative invariant verification asserting that valid domain operations preserve state consistency across randomized inputs without shrinking failures.
