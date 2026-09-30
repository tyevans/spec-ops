# How-To: Drain Backlog Queues with Concurrent Workers

This guide explains how to configure and execute persistent autonomous worker pools to continuously drain ready tasks from the refined buffer.

---

## Persistent Single-Worker Queue Drain

To run a single persistent worker process that continuously claims and executes unblocked tasks until the refined queue is exhausted:

```bash
uv run spec-ops worker --drain
```

To limit the total number of tasks drained in a single run:

```bash
uv run spec-ops worker --drain --max-tasks 5
```

---

## Concurrent Multi-Worker Batch Cycle

To process the backlog with parallel autonomous agents, run `spec-ops cycle` with concurrency enabled (defaults to 3 concurrent workers):

```bash
uv run spec-ops cycle --max-concurrency 3 --drain
```

Or execute a bounded concurrent batch:

```bash
uv run spec-ops cycle --max-concurrency 3 --max-tasks 6
```

---

## Concurrency & Conflict Protection

During concurrent execution:
1. **Isolated Worktrees**: Each worker stream executes in an isolated git worktree (`.worktrees/task-<id>`) on a dedicated task branch (`feat/<task-slug>`).
2. **Dynamic Unblocking**: When a task completes and squash-merges into `main`, dependent downstream tasks are immediately recognized as unblocked and dispatched to free worker slots.
3. **Auto-Rebase under MERGE_LOCK**: When a worker finishes, it acquires `MERGE_LOCK`. If `main` advanced due to another worker completing earlier, the worker automatically rebases onto `main` and re-verifies preflight before squash-merging.
4. **Signal-Safe Checkpointing**: Sending `SIGINT` (`Ctrl+C`) triggers a graceful shutdown trap that allows in-flight steps to checkpoint safely, ensures `MERGE_LOCK` is released cleanly, and outputs a batch summary report.

---

## Worktree Rescue and Stalled Task Recovery

When a worker process fails, times out, or encounters a gate failure, SpecOps preserves its worktree under `.worktrees/task-<id>` for diagnosis or human takeover.

### Listing Active / Stalled Worktrees

To view all in-flight or preserved worktrees:

```bash
uv run spec-ops rescue --list
```

### Rescuing and Completing a Task

To verify, rebase, and squash-merge a rescued task with guardrails:

```bash
uv run spec-ops rescue TASK-0040 --complete
```

This workflow:
1. Cleans temporary prompt files (`.task-prompt.md`).
2. Stages legitimate modifications via guardrails (reverting accidental backlog changes and unauthorized dependency edits).
3. Automatically rebases onto latest `main`.
4. Runs full preflight verification (`uv lock --check`, `uv run pytest`, `uv run spec-ops health`).
5. Under `MERGE_LOCK`, squash-merges into `main` and moves the task from `refined/` to `complete/`.
6. Prunes the worktree and deletes the feature branch.

### Discarding or Pruning Worktrees

To discard an interrupted or unneeded worktree and delete its branch:

```bash
uv run spec-ops rescue TASK-0036 --discard
```

To remove all stalled worktrees at once:

```bash
uv run spec-ops rescue --prune
```

