---
id: '0174'
title: Correct Debt Baseline File Path Discrepancy in Brownfield Adoption Guide
status: Complete
governing_adrs:
- ADR-0001
- ADR-0002
governing_prds:
- PRD-0003
governing_stories:
- US-0001
target_bc: core
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T02:23:29.738373+00:00'
commit_signature_status: SIGNED
persona: Jordan (The AI-Native Engineering Lead) & Alex (The Agentic Systems Architect)
has_signed_commits: true
---

# TASK-0174: Correct Debt Baseline File Path Discrepancy in Brownfield Adoption Guide

## Summary
The how-to guide `docs/how-to/adopt-brownfield-codebase-with-debt-baseline.md` (and published site page `adopt-brownfield-codebase-with-debt-baseline.html`) states that `spec-ops adopt` snapshots oversized files into `.spec-ops/debt-baseline.json`. However, the implementation in `src/spec_ops/core/debt_baseline.py` uses `.specops/grandfathered_debt.json` (and `specops.toml`). This creates confusion for users following the documentation.

## Problem Statement & Context
1. In `docs/how-to/adopt-brownfield-codebase-with-debt-baseline.md`:
   - Line 15: `...snapshots all existing files that exceed the 500-line file limit (ADR-0002) into .spec-ops/debt-baseline.json.`
   - Line 28: `1. Files already over 500 lines are recorded in .spec-ops/debt-baseline.json with their exact line counts at adoption time.`
2. In `src/spec_ops/core/debt_baseline.py`:
   - Line 10: `DEBT_BASELINE_FILE = ".specops/grandfathered_debt.json"`
   - `load_grandfathered_debt` only inspects `.specops/grandfathered_debt.json` and `specops.toml [invariants.file_limits]`.
3. If users check `.spec-ops/debt-baseline.json`, the file does not exist.

## Proposed Fix
1. Update `docs/how-to/adopt-brownfield-codebase-with-debt-baseline.md` to reference `.specops/grandfathered_debt.json` and explain that entries are also mirrored into `specops.toml` under `[invariants.file_limits]`.
2. Add backwards-compatibility alias check in `load_grandfathered_debt()` to also check `.spec-ops/debt-baseline.json` if present.
3. Rebuild site docs via `spec-ops docs build`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Documentation and implementation agree on baseline file locations.
2. `spec-ops docs build` cleanly re-renders the updated guide.
3. Invariant tests verify consistent documentation links.

## Acceptance Criteria

```gherkin
Scenario: Verify Correct Debt Baseline File Path Discrepancy in Brownfield Adoption Guide
  Given the system is initialized and ready
  When the user executes the workflow for "Correct Debt Baseline File Path Discrepancy in Brownfield Adoption Guide"
  Then observable outputs satisfy public contracts without backdoor tampering
  And no internal invariants are violated.
```

## Mutation Testing Scope
- Target domain module: `src/spec_ops/core/...`
- Minimum mutation kill score: >=80% under Mutmut (ADR-0009).

## Hypothesis Invariant Properties
- `@given(...)`: Generative property tests asserting state invariants across randomized inputs without shrinking failures (ADR-0009).

## Scope & Architectural Invariants
- Target Bounded Context: `core` (single bounded context)
- Estimated Implementation Diff: <400 lines
- File Length Limit: all touched source files strictly <500 lines (ADR-0002).
