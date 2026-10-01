---
id: '0174'
title: Correct Debt Baseline File Path Discrepancy in Brownfield Adoption Guide
status: Proposed
governing_adrs:
- ADR-0001
- ADR-0002
target_bc: core
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
