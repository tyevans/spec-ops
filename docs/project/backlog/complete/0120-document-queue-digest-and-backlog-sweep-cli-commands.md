---
id: '0120'
title: Document spec-ops queue digest and backlog sweep in Diataxis CLI Reference
status: Complete
dependencies:
- TASK-0067
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0006
governing_prds:
- PRD-0005
governing_stories:
- US-0077
target_bc: backlog
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T00:22:51.342065+00:00'
mutation_scope: src/spec_ops/scaffold/diataxis.py
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0120: Document spec-ops queue digest and backlog sweep in Diataxis CLI Reference

## Summary
Document `spec-ops queue digest` and `spec-ops backlog sweep` CLI commands in the Diataxis CLI reference (`docs/reference/cli.md`) and the CLI reference scaffold template (`src/spec_ops/scaffold/diataxis.py`).

## Problem Statement & Context
During execution of `spec-ops rescue TASK-0067 --complete`, the preflight test stage failed because `spec-ops docs audit` detected CLI documentation drift:
- `spec-ops backlog sweep` is implemented in CLI but missing from `docs/reference/cli.md`
- `spec-ops queue digest` is implemented in CLI but missing from `docs/reference/cli.md`

Per the SpecOps Dogfooding / SDLC Orchestration Failure Invariant defined in `AGENTS.md`, any orchestration failure is an actionable task documented as a defect in the backlog and remediated.

## Resolution
1. Add `spec-ops queue digest` and `spec-ops backlog sweep` to `docs/reference/cli.md` under the Command Reference table with corresponding arguments and descriptions.
2. Synchronize `DEFAULT_REFERENCE_CLI` template in `src/spec_ops/scaffold/diataxis.py` so that newly scaffolded projects remain synchronized with all CLI entry points.
3. Validate synchronization using `spec-ops docs audit` and existing unit/BDD tests.
