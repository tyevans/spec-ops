---
id: '0124'
title: Filter Existing Filesystem Directories in Init Wizard Property Tests
status: Complete
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0068
target_bc: scaffold
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T00:52:11.623827+00:00'
mutation_scope: src/spec_ops/scaffold/wizard.py
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0124: Filter Existing Filesystem Directories in Init Wizard Property Tests

## Summary
Update `test_property_invalid_profile_zero_pollution` in `tests/test_init_wizard_properties.py` to filter out strings that resolve to existing directories on disk (e.g. `spikes`, `docs`, `src`), ensuring only truly invalid profile identifiers are tested for rejection.

## Problem Statement & Context
During preflight test execution for `TASK-0104`, Hypothesis generated `invalid_profile = 'spikes'` in `test_property_invalid_profile_zero_pollution`. Because the repository contains a `spikes/` directory, `load_profile_definition("spikes")` resolved it as a valid directory-based profile per ADR-0002/composer rules, causing the expected `InitValidationError` to not be raised.

Per the SpecOps Dogfooding / SDLC Orchestration Failure Invariant defined in `AGENTS.md`, any orchestration failure is an actionable task documented as a defect in the backlog and remediated.

## Resolution
1. In `tests/test_init_wizard_properties.py`, add `and not Path(s).exists()` to the Hypothesis strategy filter for `invalid_profile`.
2. Verify all property test examples pass without shrinking errors.
