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
