# How-To: Resolve Task Dependency Deadlocks and Cycles

This guide explains how to detect circular task dependencies, compute minimal feedback arc cuts, and resolve dependency deadlocks using `spec-ops graph deadlock` governed by [ADR-0005](../project/adrs/accepted/adr-0005-strict-backlog-isolation-and-task-worktree-lifecycle.md) and [ADR-0017](../project/adrs/accepted/adr-0017-deterministic-dag-topology-and-cycle-resolution.md).

---

## Overview

In multi-agent collaborative workflows, autonomous workers and human architects continuously author tasks with explicit dependencies. When circular dependencies form (e.g. `TASK-0010` depends on `TASK-0011` which depends on `TASK-0010`), neither task can satisfy the Definition of Ready (DoR), resulting in an execution deadlock.

The `spec-ops graph deadlock` engine:
- Traverses the entire task dependency digraph across all backlog folders
- Identifies Strongly Connected Components (SCC) using Tarjan's algorithm
- Computes the minimum feedback arc set (FAS) to find the optimal minimal set of edges to prune
- Provides automated edge resolution (`--resolve`) with safe simulation (`--dry-run`)

---

## Auditing Backlog Dependency Deadlocks

To check whether the task dependency graph is a valid Directed Acyclic Graph (DAG):

```bash
uv run spec-ops graph deadlock
```

If the graph is clean, the command exits with code `0`:
```text
=== SpecOps Task Dependency Deadlock Analysis ===
Nodes Analyzed: 182
Dependencies:   270

✅ Traceability Invariant Met: Zero dependency deadlocks or circular cycles detected.
   The task dependency graph is a valid Directed Acyclic Graph (DAG).
```

---

## Diagnosing Circular Dependency Cycles

When circular dependencies exist, `spec-ops graph deadlock` outputs the cycle paths and minimal cut recommendations, exiting with code `1`:

```text
=== SpecOps Task Dependency Deadlock Analysis ===
Nodes Analyzed: 45
Dependencies:   62

❌ Dependency Deadlocks Detected: 1 circular cycle(s) found.

  Cycle 1: TASK-0012 -> TASK-0013 -> TASK-0014 -> TASK-0012
    Recommended Break: Remove dependency edge 'TASK-0014 -> TASK-0012'
    Rationale:         Breaking 'TASK-0014' -> 'TASK-0012' resolves circular wait in component ['TASK-0012', 'TASK-0013', 'TASK-0014'].

Recommended Minimal Cut Set (1 edge(s)):
  • Prune 'TASK-0014' -> 'TASK-0012'
```

---

## Simulating and Applying Automated Dependency Cuts

To simulate pruning the cyclic edges without modifying task markdown files:

```bash
uv run spec-ops graph deadlock --resolve --dry-run
```

To automatically apply the recommended edge cuts to the task files:

```bash
uv run spec-ops graph deadlock --resolve
```

---

## Exporting Deadlock Diagnostics to JSON

For automated agent scripts and CI pipelines, pass `--json`:

```bash
uv run spec-ops graph deadlock --json
```

---

## Verifying Documentation Drift

To confirm documentation references and CLI arguments stay synchronized:

```bash
uv run spec-ops docs audit
uv run spec-ops docs build
```
