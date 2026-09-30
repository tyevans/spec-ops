# How to Inspect Task Dependencies and Manage Backlog Blockers

This guide demonstrates how to inspect task dependency hierarchies, analyze delivery horizons ("execution waves"), flag tasks blocked by technical unknowns, and resolve blockers through governed architectural spikes.

---

## 1. Inspecting the Task Dependency Tree

To visualize what work is unblocked and ready to start, versus what work is blocked downstream:

```bash
spec-ops queue tree
```

By default, this renders an **Execution Dependency Tree** rooted at ready or unblocked tasks, showing the subsequent tasks that will be unlocked upon their completion.

### Prerequisite Inspection ("Blocked By" View)

To trace why a specific task is blocked and view its upstream dependency chain:

```bash
spec-ops queue tree --task TASK-0054 --direction blocked-by
```

To include all completed historical prerequisites in the tree:

```bash
spec-ops queue tree --task TASK-0054 --direction blocked-by --all
```

---

## 2. Analyzing Delivery Horizons (Execution Waves)

To view the sequential delivery stages of your backlog:

```bash
spec-ops queue tree --waves
```

- **Wave 0**: Unblocked tasks with all prerequisites met (can be claimed and executed immediately).
- **Wave 1**: Tasks blocked solely by Wave 0 tasks (will unlock once Wave 0 completes).
- **Wave 2+**: Subsequent downstream horizons.
- **Choke Points**: Highlights bottleneck tasks whose completion unlocks the highest count of downstream tasks.

---

## 3. Flagging a Task Blocked by a "Big Unknown"

When an engineer or autonomous coding assistant encounters a major unknown (e.g. uncertain API performance, ambiguous architecture, or unresolved technical questions), flag the task as blocked:

```bash
spec-ops queue block TASK-0052 \
  --question "How do we isolate git worktree garbage collection without destroying active diagnostic logs?" \
  --type unknown \
  --raised-by Alex
```

### Automatically Scaffolding an Architectural Spike

If the unknown requires empirical investigation or prototyping before work can continue, add the `--spike` flag:

```bash
spec-ops queue block TASK-0052 \
  --question "Can tree-sitter AST queries run sub-50ms in Python without native bindings?" \
  --spike \
  --timebox 2h
```

SpecOps will automatically:
1. Mark `TASK-0052` as `Blocked (Unknown)`.
2. Author a new spike task (`SPIKE-XXXX`) in `docs/project/backlog/proposed/`.
3. Scaffold an isolated test harness in `spikes/spike_XXXX/`.
4. Add `SPIKE-XXXX` to `TASK-0052`'s dependencies.
5. Synchronize `docs/project/backlog/PRIORITY.md`.

---

## 4. Querying Active Project Blockers

To view all active blockers and unresolved questions across the project:

```bash
spec-ops queue blockers
```

For machine-readable JSON output suitable for autonomous agent dispatchers:

```bash
spec-ops queue blockers --json
```

---

## 5. Resolving an Unknown and Unblocking the Task

Once the question is resolved (either via `spec-ops spike graduate` or through an architectural decision), unblock the task:

```bash
spec-ops queue unblock TASK-0052 \
  --resolution "Validated tree-sitter caching strategy; p95 latency is 12ms." \
  --adr ADR-0020
```

SpecOps records the resolution and ADR reference in the task frontmatter, re-evaluates upstream dependencies, and restores the task to `Refined` (if all prerequisites are fulfilled) or `Proposed`.
