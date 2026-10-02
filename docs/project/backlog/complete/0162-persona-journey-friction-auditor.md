---
id: '0162'
title: Autonomous User Persona Journey Friction Auditor and Heuristic Evaluator
status: Complete
dependencies:
- TASK-0110
- TASK-0145
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
governing_prds:
- PRD-0003
- PRD-0006
governing_stories:
- US-0110
- US-0117
target_bc: prd
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-02T00:41:40.956660+00:00'
commit_signature_status: SIGNED
has_signed_commits: true
---

# TASK-0162: Autonomous User Persona Journey Friction Auditor and Heuristic Evaluator

## Summary
Implement an autonomous user persona journey friction auditor and heuristic evaluator (`src/spec_ops/prd/persona_friction.py`). Governed by PRD-0003 and PRD-0006, this engine correlates persona pain points defined in `docs/project/user_stories/PERSONAS.md` against user journeys and CLI commands, computing cognitive friction scores and surfacing usability bottlenecks (`spec-ops prd friction`).

## Problem Statement & Context
Even with exhaustive Gherkin scenarios and passing unit tests, CLI interactions can suffer from excessive friction (too many required arguments, opaque error messages, multi-step ceremonies). An automated persona friction auditor checks proposed workflows against target persona archetypes, flagging operations that violate ease-of-use standards.

## Key Requirements & Scope
1. **Persona Friction Auditor (`src/spec_ops/prd/persona_friction.py`)**:
   - Parses persona definitions (Alex, Sasha, Taylor, Morgan, Jordan, Riley) and their pain points.
   - Analyzes CLI commands, argument counts, interactive vs headless modes, and user stories.
   - Calculates a deterministic friction index [0.0 - 10.0] based on command depth, step count, and ceremony.
   - Recommends ergonomic simplifications (e.g. smart defaults, single-flag shortcuts).
2. **Friction CLI (`spec-ops prd friction [--persona <name>] [--json] [--threshold <N>]`)**:
   - Outputs a friction diagnostic report highlighting high-friction workflows.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Module in `src/spec_ops/prd/persona_friction.py` must stay strictly under 400 lines (ADR-0002).
- **Persona Alignment (ADR-0001)**: Relies on canonical persona definitions in `docs/project/user_stories/PERSONAS.md`.
- **Mutation Testing Scope**: Target module `src/spec_ops/prd/persona_friction.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Auditing friction score for persona workflows
```gherkin
Given established user personas and CLI command definitions
When the developer runs spec-ops prd friction
Then the engine computes friction indices across persona touchpoints
And displays actionable recommendations for reducing operational ceremony
```

### Scenario 2: Flagging workflows exceeding friction threshold
```gherkin
Given a workflow with high ceremony exceeding the configured friction threshold
When spec-ops prd friction is evaluated with threshold check
Then high-friction commands are flagged with remediation hints
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that computed friction scores are bounded within [0.0, 10.0] across arbitrary input strings and command parameter counts.
