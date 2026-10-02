# How-To: Manage Worker Lease Heartbeats and Reclaim Zombie Claims

This guide explains how to track active worker process leases, record liveness heartbeats, and automatically reclaim dead or abandoned task claims using `spec-ops worker lease`, governed by [ADR-0005](../project/adrs/accepted/adr-0005-worktree-concurrency-and-backlog-isolation.md) and [ADR-0012](../project/adrs/accepted/adr-0012-zero-trust-worker-process-sandboxing.md).

---

## Overview

In concurrent multi-agent architectures, workers operate in isolated git worktrees. If a worker process crashes, experiences an out-of-memory termination, or disconnects unexpectedly, its claimed task could remain indefinitely locked in an `In-Progress` state.

The Worker Lease Manager provides:
- Cryptographic lease tokens assigned upon task claim with configurable TTL (default 300 seconds)
- Monotonic heartbeat extensions recorded by long-running workers
- Host operating system PID liveness verification
- Automated zombie claim revocation returning abandoned tasks to `Refined` status for reallocation

---

## Inspecting Active Worker Leases

To view all currently registered worker leases and their liveness state:

```bash
uv run spec-ops worker lease --status
```

Output:
```text
=== SpecOps Worker Lease Status ===
⚡ [ACTIVE] TASK-0042: Worker=spec-ops-worker-1, PID=14022, Reason=Active valid lease with live process
    Expires: 2026-10-01T18:35:00+00:00 | Last Heartbeat: 2026-10-01T18:30:00+00:00
⚠️  [ZOMBIE] TASK-0045: Worker=spec-ops-worker-2, PID=12910, Reason=Zombie lease: expired and host PID 12910 dead
    Expires: 2026-10-01T18:15:00+00:00 | Last Heartbeat: 2026-10-01T18:10:00+00:00
```

To output machine-readable telemetry as JSON:

```bash
uv run spec-ops worker lease --status --json
```

---

## Recording Worker Heartbeats

Long-running workers periodically update their heartbeat to extend lease validity and prevent premature eviction:

```bash
uv run spec-ops worker lease --heartbeat --task TASK-0042
```

Output:
```text
💓 Heartbeat recorded for TASK-0042 (PID 14022). Expires at 2026-10-01T18:40:00+00:00.
```

---

## Reclaiming Zombie Worker Claims

To reconcile all active claims and automatically restore dead or abandoned tasks to the ready backlog:

```bash
uv run spec-ops worker lease --reclaim
```

Output:
```text
=== Worker Lease Reconciliation & Zombie Claim Reclaimer ===
Active Leases:    1
Reclaimed Claims: 1
  🔄 Revoked zombie claim TASK-0045 (Zombie lease: expired and host PID 12910 dead) -> Restored to Refined
  ⚡ Active lease TASK-0042 held by worker spec-ops-worker-1 (PID 14022)
```

To simulate claim reconciliation without modifying task files:

```bash
uv run spec-ops worker lease --reclaim --dry-run
```
