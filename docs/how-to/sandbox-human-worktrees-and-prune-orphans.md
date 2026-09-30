# How to Sandbox Human Worktrees and Prune Orphaned Workspaces

This guide explains how human engineers can spawn conflict-free git worktrees for task development, safely integrate finished work into `main` under merge locks, and prune abandoned or orphaned worktrees without risking dirty local state.

---

## Overview

SpecOps enforces git worktree isolation to guarantee that concurrent workers and human developers never modify shared backlog files on feature branches (ADR-0005). The `spec-ops worktree` and `spec-ops rescue prune` commands provide developer ergonomics that abstract low-level `git worktree` commands, configure UV environment symlinks automatically, and safeguard active uncommitted changes.

---

## Step 1: Spawn a Clean Development Worktree

To pick up an unassigned task from `docs/project/backlog/refined/`, spawn an isolated worktree:

```bash
spec-ops worktree start TASK-0042
```

This command automatically:
1. Validates that the task is in `refined/` status and unblocked.
2. Creates an isolated directory at `.worktrees/task-0042`.
3. Creates and checks out a dedicated branch (`feat/task-0042` or `task/task-0042`).
4. Links the root `.venv` or UV workspace configuration so tools (`pytest`, `spec-ops`) work immediately.
5. Records the developer claim in task frontmatter on `main`.

Navigate into the newly provisioned worktree:

```bash
cd .worktrees/task-0042
```

---

## Step 2: Implement and Verify Changes in Isolation

Develop your changes using test-driven development. Run local verification inside the worktree:

```bash
uv run pytest
uv run spec-ops health
```

Your work is completely isolated from other branches and workers running concurrently.

---

## Step 3: Finish and Integrate Under Merge Lock

Once all tests pass and documentation invariants are met, finalize the task from within the worktree directory:

```bash
spec-ops worktree finish
```

Or execute it from the repository root by specifying the task ID:

```bash
spec-ops worktree finish --task-id TASK-0042
```

The finish workflow:
1. Runs full preflight validation (`uv lock --check`, `pytest`, `spec-ops health`).
2. Acquires `MERGE_LOCK` to ensure zero merge races against autonomous agent workers.
3. Automatically rebases onto `main` and squash-merges with structured RFC-822 trailers (`SpecOps-Task: TASK-0042`).
4. Atomically transitions the task file from `refined/` to `complete/` and syncs `PRIORITY.md`.
5. Removes `.worktrees/task-0042` and deletes the feature branch cleanly.

---

## Step 4: Preview and Prune Orphaned Worktrees

Interrupted autonomous agent cycles or abandoned tasks can leave stale directories in `.worktrees/`. 

Preview reclaimable disk space and candidate worktrees without making any changes:

```bash
spec-ops rescue prune --dry-run
```

Execute garbage collection to remove merged worktrees and dangling agent branches:

```bash
spec-ops rescue prune
```

### Safety Protections

`spec-ops rescue prune` enforces strict safety invariants:
- **Dirty State Guard**: Any worktree containing uncommitted modifications or untracked files is skipped with a protective warning.
- **Human Claim Guard**: Worktrees claimed by human developers (`claimed_by: human` or active developer handles) are never pruned automatically.
- **Git Prune Sync**: Automatically invokes `git worktree prune` to keep git internal metadata clean.

---

## Step 5: Triage and Takeover Preserved Agent Worktrees

When an autonomous worker session exhausts its self-healing retries, its isolated worktree is preserved under `.worktrees/task-<id>`.

1. **Interactive Failure Triage**: Inspect categorized root causes (file length invariants, test suite failures, lockfile drift, git status) and AST diffs:
   ```bash
   spec-ops rescue triage TASK-0012
   ```

2. **Diagnostic Human Takeover**: Transfer task claim from autonomous worker to human developer and provision workspace:
   ```bash
   spec-ops rescue takeover TASK-0012
   ```

3. **Verify and Finalize**: Implement fixes inside `.worktrees/task-0012`, then verify preflight and squash-merge into `main`:
   ```bash
   spec-ops rescue TASK-0012 --complete
   ```

---

## Step 6: Rapid Iteration with Fast Incremental Preflight Runner

When troubleshooting a rescued worktree, rerunning the entire multi-minute preflight suite for each small change introduces significant latency. Use the incremental test runner to isolate broken checks:

1. **Re-run Only Failed Steps**:
   Rerun only the previously failed check (skipping cached passes like lockfile validation and invariant checks):
   ```bash
   spec-ops rescue test --only-failed
   ```

2. **Isolate a Specific Preflight Step**:
   Target an individual gate or check for sub-second feedback during iterative fixes:
   ```bash
   spec-ops rescue test --step lint
   ```

3. **Mandatory Full Revalidation on Completion**:
   When completing rescue with `spec-ops rescue <task-id> --complete`, incremental caches are automatically bypassed to enforce an un-truncated, full preflight run before merging into `main`.

