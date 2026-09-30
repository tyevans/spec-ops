---
id: 0019
title: Supply-Chain Sandboxing and Lockfile Preflight Enforcement
status: Complete
created: 2026-09-29
completed: 2026-09-29
dependencies:
- TASK-0011
governing_adrs:
- ADR-0001
- ADR-0004
governing_prds:
- PRD-0001
governing_stories:
- US-0005
target_bc: core
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0019: Supply-Chain Sandboxing and Lockfile Preflight Enforcement

## Summary
Incorporate dependency lockfile verification (`uv lock --check`) into default preflight gates and define execution sandboxing boundaries for autonomous agent sessions to satisfy security requirements (Sasha).

## Definition of Done (Blackbox Frontdoor TDD)
1. Preflight verifies lockfile consistency and blocks tasks with desynchronized lockfiles.
2. Integration tests verify worker execution logs metadata and prevents directory escape.
3. Zero files exceed 500 lines.

## Completion Summary
- Added `enforce_lockfile: bool = True` to [`QualitySettings`](../../../src/spec_ops/config/models.py).
- Enhanced `run_preflight()` in [`BacklogWorkerEngine`](../../../src/spec_ops/backlog/worker.py) to automatically execute `uv lock --check` before test runs whenever `uv.lock` exists.
- Injected isolated environment variables (`SPEC_OPS_WORKTREE`, `PWD`) during `invoke_agent` execution.
- Added cryptographic/audit provenance commit metadata (Task ID, Governing ADRs, Provenance trail) to all automated worker commits.
- Added test coverage in [`tests/test_backlog_health_and_curator.py`](../../../tests/test_backlog_health_and_curator.py).
- All source files conform to Hard Invariant 6 (<500 lines).
