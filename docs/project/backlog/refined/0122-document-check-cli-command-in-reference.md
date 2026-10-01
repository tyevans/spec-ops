---
id: '0122'
title: Document spec-ops check in Diataxis CLI Reference
status: Refined
dependencies:
- TASK-0055
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
governing_prds:
- PRD-0004
governing_stories:
- US-0091
target_bc: rescue
---

# TASK-0122: Document spec-ops check in Diataxis CLI Reference

## Summary
Document the `spec-ops check` command in `docs/reference/cli.md` and update `DEFAULT_REFERENCE_CLI` in `src/spec_ops/scaffold/diataxis.py` to eliminate Diataxis documentation drift.

## Problem Statement & Context
During preflight validation for `TASK-0055`, `spec-ops docs audit` detected CLI documentation drift:
```
Command 'spec-ops check' is implemented in CLI but missing from docs/reference/cli.md
```
`spec-ops check` provides sub-second single-file invariant diagnostic checks for real-time IDE linting (`--fast`, `--file`, `--format text|json|sarif`), but its CLI command entry was not added to the reference documentation table.

Per the SpecOps Dogfooding / SDLC Orchestration Failure Invariant defined in `AGENTS.md`, any orchestration failure is an actionable task documented as a defect in the backlog and remediated.

## Resolution
1. Add `spec-ops check` to `docs/reference/cli.md` under the Command Reference table with its argument signature and summary.
2. Update `DEFAULT_REFERENCE_CLI` in `src/spec_ops/scaffold/diataxis.py`.
3. Validate synchronization using `spec-ops docs audit`.
