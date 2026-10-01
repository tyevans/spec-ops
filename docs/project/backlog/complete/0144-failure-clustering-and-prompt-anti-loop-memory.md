---
id: '0144'
title: Autonomous Failure Post-Mortem Clustering and Prompt Anti-Loop Synthesizer
status: Complete
dependencies:
- TASK-0084
- TASK-0134
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0020
governing_prds:
- PRD-0004
governing_stories:
- US-0084
- US-0089
target_bc: rescue
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T11:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0144: Autonomous Failure Post-Mortem Clustering and Prompt Anti-Loop Synthesizer

## Summary
Implement automated failure post-mortem clustering and dynamic prompt anti-loop constraint synthesis (`src/spec_ops/rescue/failure_clustering.py`). In accordance with ADR-0020 and PRD-0004, this engine groups historical worker attempt failures across tasks into common anti-patterns (e.g. mock tampering, timeout churn, line limit violations) and synthesizes explicit negative prompt instructions into `.task-prompt.md` to prevent subsequent worker sessions from repeating known failure modes.

## Problem Statement & Context
When parallel autonomous agents execute tasks, multiple workers across different tasks often encounter similar stumbling blocks (such as introducing private test mocks or misinterpreting library interfaces). Storing failure memory purely on individual tasks helps single tasks, but does not generalize across the fleet. ADR-0020 specifies failure clustering across tasks to synthesize global negative prompt constraints.

## Key Requirements & Scope
1. **Failure Clustering Engine (`src/spec_ops/rescue/failure_clustering.py`)**:
   - Analyzes all `failure_history` entries across `docs/project/backlog/` tasks.
   - Clusters failure reasons into categorical failure archetypes using keyword and regex distance metrics.
2. **Negative Constraint Synthesizer**:
   - Translates failure clusters into actionable negative prompt guidance (`## Prior Fleet Failures & Prohibitions`).
   - Automatically injects these constraints during task prompt hydration in `TaskClaimer`.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Failure clustering module in `src/spec_ops/rescue/failure_clustering.py` must stay strictly under 400 lines (ADR-0002).
- **Anti-Loop Memory Invariant (ADR-0020)**: Identified failure modes must produce deterministic negative prompt prohibitions without hallucination.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/rescue/failure_clustering.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Clustering recurrent failure modes across tasks
```gherkin
Given multiple backlog tasks with recorded failure histories citing mock backdoors
When the failure clustering engine analyzes the backlog
Then a common failure cluster for "Mock Backdoor Tampering" is identified
And associated with ADR-0003
```

### Scenario 2: Hydrating prompt with synthesized negative constraints
```gherkin
Given an identified failure cluster for mock backdoors
When a new worker claims a related task
Then the generated ".task-prompt.md" includes explicit negative prompt instructions forbidding mocks
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary list of failure history records, clustering operates deterministically without dropping entries or producing unhandled exceptions.
