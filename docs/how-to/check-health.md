# How-To: Verify Codebase Health and File Length Limits

This guide covers running `spec-ops health` in local development and continuous integration.

---

## Running Health Checks

To run the health check locally:

```bash
spec-ops health
```

---

## Interpreting Output

A successful health check verifies:
1. **File Length Limit**: Zero source files exceed the configured threshold (default: <500 lines).
2. **Backlog Buffer Status**: Number of tasks in `refined/` matches target buffer size (~10).
3. **PRIORITY.md Sync**: Verifies that every task referenced in `PRIORITY.md` exists in its claimed directory on disk.

```text
=== SpecOps Health Check (MyApp) ===
Limit: <500 lines per file
✅ Invariant Met: Zero source files exceed length limit.

Backlog State:
   Complete Tasks: 8
   Refined Buffer: 6 (OPTIMAL)
   Proposed Tasks: 2
✅ PRIORITY.md is synchronized with disk state.
```

---

## Local Pre-Commit Invariant Gate

SpecOps provides the `spec-ops-health` local pre-commit hook to prevent bad commits before they are staged or committed:
- **Hard Invariant (<500 lines)**: Files with 500 lines or more abort the commit with `File Length Violation: <path> (<lines> lines > 500 line limit)`.
- **Proactive Refactoring Warnings (>=400 lines)**: Emits a non-blocking warning `⚠️ Proactive Refactoring Warning: <path> (<lines> lines >= 400 line warning threshold)` alerting the developer to decompose approaching modules.
- **PRIORITY.md Synchronization**: Confirms that task references in `docs/project/backlog/PRIORITY.md` match disk state.

To install the native pre-commit hook in any repository:
```bash
python3 -c "from spec_ops.worker.hooks import install_pre_commit_hook; from pathlib import Path; install_pre_commit_hook(Path('.'))"
```

---

## Multi-Stage Preflight Validation Pipeline

Autonomous workers execute preflight verification through a deterministic sequential pipeline with early fast-fail capability:
1. **Stage 1 (`lockfile`)**: `uv lock --check` verifies dependency lockfile synchronization. If lockfile drift occurs, the pipeline halts immediately without wasting compute running tests.
2. **Stage 2 (`health`)**: `uv run spec-ops health` checks file length limits, constitution drift, and PRIORITY sync.
3. **Stage 3 (`test`)**: `uv run pytest` executes the test suite.

If preflight fails in an autonomous worktree, exact failure diagnostics and line numbers are written to `.task-prompt.md` for self-healing across up to 3 retry attempts. If retries are exhausted, the worktree is preserved at `.worktrees/<task-id>` and `spec-ops rescue <task-id>` is emitted.

