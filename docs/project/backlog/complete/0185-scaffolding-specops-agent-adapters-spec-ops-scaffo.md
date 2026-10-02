---
id: 0185
title: Implement Scaffolding SpecOps agent adapters (`spec-ops scaffold --agents antigravity`)
  generates `.agents/skills/spec-ops/SKILL.md`.
status: Complete
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0004
governing_prds:
- PRD-0006
governing_stories:
- US-0117
target_bc: core
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T03:29:05.404210+00:00'
commit_signature_status: SIGNED
has_signed_commits: true
---

# TASK-0185: Implement Scaffolding SpecOps agent adapters (`spec-ops scaffold --agents antigravity`) generates `.agents/skills/spec-ops/SKILL.md`.

## Summary
Fulfills Outcome 2 of PRD-0006 for persona Alex (The Agentic Systems Architect) & Jordan (The AI-Native Engineering Lead).
Target capability: Scaffolding SpecOps agent adapters (`spec-ops scaffold --agents antigravity`) generates `.agents/skills/spec-ops/SKILL.md`..

## Problem Statement & Context
Delivers an INVEST-compliant vertical slice in bounded context `core`.
Estimated implementation diff: <400 lines.
File length limit: all touched source files strictly <500 lines (ADR-0002).

## Acceptance Criteria

```gherkin
Scenario: Verify Scaffolding SpecOps agent adapters (`spec-ops scaffold --agents antigravity`) generates `.agents/skills/spec-ops/SKILL.md`.
  Given the system is initialized and ready
  When the user executes the workflow for "Implement Scaffolding SpecOps agent adapters (`spec-ops scaffold --agents antigravity`) generates `.agents/skills/spec-ops/SKILL.md`."
  Then observable outputs satisfy public contracts without backdoor tampering
  And no internal invariants are violated.
```

## Mutation Testing Scope
- Target domain module: `src/spec_ops/core/...`
- Minimum mutation kill score: >=80% under Mutmut (ADR-0009).

## Hypothesis Invariant Properties
- `@given(...)`: Generative property tests asserting state invariants across randomized inputs without shrinking failures (ADR-0009).

## Definition of Done (Blackbox Frontdoor TDD)
1. Public interfaces or standard domain contracts implemented.
2. Verified via automated blackbox tests without private backdoor manipulation (ADR-0003).
3. All new source files strictly under 500 lines (ADR-0002).
