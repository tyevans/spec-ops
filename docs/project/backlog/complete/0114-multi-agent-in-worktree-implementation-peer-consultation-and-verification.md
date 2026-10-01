---
id: '0114'
title: Multi-Agent In-Worktree Implementation, Peer Consultation, and Verification
  Loop
status: Complete
dependencies:
- TASK-0109
- TASK-0113
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0006
- ADR-0007
- ADR-0008
- ADR-0009
- ADR-0010
- ADR-0011
- ADR-0012
governing_prds:
- PRD-0006
governing_stories:
- US-0117
target_bc: worker
---

# TASK-0114: Multi-Agent In-Worktree Implementation, Peer Consultation, and Verification Loop

## Summary
Implement a high-fidelity multi-agent coordination loop for in-worktree task execution (`spec-ops worker orchestrate`) where specialized implementation subagents consult approved PMaC specifications (`docs/project/`), collaborate with peer review agents to cross-check contracts, execute blackbox frontdoor TDD, and pass strict preflight gates before requesting PR integration.

## Problem Statement & Context
Existing workers operate primarily in isolation, frequently missing broader architectural context or failing to consult neighboring bounded contexts when making interface decisions. A true "company in a box" orchestrator requires active peer consultation: implementation subagents must actively check approved specifications, request feedback from review subagents, and self-heal failed preflight checks before escalating to human maintainers.

## User Stories & Scenarios Satisfied
- **US-0117: Autonomous Full-Lifecycle SDLC Orchestrator Skill & Multi-Agent Coordination**
  - *Scenario: In-Worktree Subagent Peer Consultation*
    - Given an implementation subagent working in an isolated worktree on "TASK-XXXX"
    - When the subagent defines an interface change touching another bounded context
    - Then the orchestrator dispatches a review subagent to inspect the interface against active ADRs
    - And provides feedback to the implementation agent before commit staging.
  - *Scenario: Preflight Verification and Self-Healing*
    - Given an in-worktree test or health check failure
    - When the implementation agent runs preflight verification
    - Then actionable AST diagnostics are provided for iterative self-healing up to max attempts.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Orchestration worker coordinator in `src/spec_ops/worker/orchestrator.py` must stay strictly under 400 lines (ADR-0002).
- **Strict Backlog Isolation (ADR-0005)**: Feature branches remain strictly forbidden from modifying `docs/project/backlog/`.
- **Mutmut Mutation Scope**: Peer consultation protocols and preflight validation gates achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. CLI command `spec-ops worker orchestrate` drives multi-agent task execution.
2. Peer consultation rules enforced: subagents must read cited ADRs and stories before generating code.
3. Preflight gates (`spec-ops health`, `uv run pytest`, `uv lock --check`) verified automatically.
4. 100% test pass rate verifying observable contracts without private mock backdoors.

## Acceptance Criteria

### Scenario 1: In-Worktree Subagent Peer Consultation*
```gherkin
Given the system is initialized and ready
When the user executes the workflow for "Multi-Agent In-Worktree Implementation, Peer Consultation, and Verification Loop"
Then In-Worktree Subagent Peer Consultation*
And observable outputs satisfy public contracts without backdoor tampering.
```

### Scenario 2: Preflight Verification and Self-Healing*
```gherkin
Given the system is initialized and ready
When the user executes the workflow for "Multi-Agent In-Worktree Implementation, Peer Consultation, and Verification Loop"
Then Preflight Verification and Self-Healing*
And observable outputs satisfy public contracts without backdoor tampering.
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative invariant verification asserting that valid domain operations preserve state consistency across randomized inputs without shrinking failures.
