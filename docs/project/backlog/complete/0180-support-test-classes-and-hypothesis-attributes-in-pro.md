---
id: TASK-0180
title: Support Test Classes and Modern Hypothesis Method Attributes in Property Runner
  Discovery
status: Complete
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0004
governing_prds:
- PRD-0003
governing_stories:
- US-0001
target_bc: core
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T03:09:45.734522+00:00'
commit_signature_status: SIGNED
persona: Jordan (The AI-Native Engineering Lead) & Alex (The Agentic Systems Architect)
has_signed_commits: true
---

## Summary
In `src/spec_ops/core/properties_runner.py`, `discover_property_tests` only inspects module-level attributes matching `attr_name.startswith("test_")`.

This causes tests structured within test classes (e.g. `class TestIntervalProperties: def test_...`) or standard `pytest` class fixtures to be completely ignored.

Additionally, detection of Hypothesis tests uses:
`is_hypo = getattr(fn, "is_hypothesis_test", False) or hasattr(fn, "hypothesis") or "property" in attr_name`
which does not detect modern Hypothesis decorators (which attach `_hypothesis_internal_use_raw_state` or `@given` wrapped attributes) unless `"property"` is literally in the function name.

## Requirements
1. In `discover_property_tests`, inspect both module-level test functions and methods of test classes (`class Test...:`).
2. Expand Hypothesis test detection to inspect `getattr(fn, "_hypothesis_internal_use_raw_state", None)` or check if `@given` wrapped the callable.

## Acceptance Criteria

```gherkin
Scenario: Verify Support Test Classes and Modern Hypothesis Method Attributes in Property Runner Discovery
  Given the system is initialized and ready
  When the user executes the workflow for "Support Test Classes and Modern Hypothesis Method Attributes in Property Runner Discovery"
  Then observable outputs satisfy public contracts without backdoor tampering
  And no internal invariants are violated.
```

## Mutation Testing Scope
- Target domain module: `src/spec_ops/core/...`
- Minimum mutation kill score: >=80% under Mutmut (ADR-0009).

## Scope & Architectural Invariants
- Target Bounded Context: `core` (single bounded context)
- Estimated Implementation Diff: <400 lines
- File Length Limit: all touched source files strictly <500 lines (ADR-0002).
