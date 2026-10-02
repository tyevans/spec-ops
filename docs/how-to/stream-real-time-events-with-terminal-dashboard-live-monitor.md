# How-To: Stream Real-Time Events with Terminal Dashboard Live Monitor

This guide explains how to monitor active worker fleets, inspect live orchestration events, and evaluate system health in terminal and headless CI environments using `spec-ops monitor live`, governed by [ADR-0008](../project/adrs/accepted/adr-0008-tui-driven-workflow-monitoring.md) and [ADR-0010](../project/adrs/accepted/adr-0010-zero-broker-event-ledger.md).

---

## Overview

When running multi-agent worker teams in headless environments, containers, or terminal multiplexers (such as tmux), developers need real-time operational visibility without opening an external web browser.

The `spec-ops monitor live` dashboard provides:
- A Rich-based multi-tab console interface
- Dynamic worker telemetry showing active worktrees, worker PIDs, lease expiries, and host CPU/memory utilization
- Real-time event streaming subscribed directly to the in-process `EventStreamer`
- Backlog health metrics including JIT buffer status and file length invariant verification
- Seamless headless snapshot mode for CI/CD pipelines

---

## Launching the Interactive Live Monitor

To start the interactive terminal monitor:

```bash
uv run spec-ops monitor live
```

### Keybindings & Navigation

| Key | Action |
|---|---|
| `q` or `Q` | Exit the live monitor and return to shell |
| `r` or `R` | Force immediate refresh of dashboard views |
| `Tab` or `Space` | Cycle through dashboard tabs (`Workers` -> `Events` -> `Health`) |
| `1` | Switch directly to **Workers View** |
| `2` | Switch directly to **Events View** |
| `3` | Switch directly to **Health View** |

---

## Configuring the Refresh Interval & Initial Tab

You can customize the polling interval and select an initial active tab:

```bash
uv run spec-ops monitor live --interval 0.5 --tab events
```

---

## Running in Headless CI Environments

In non-interactive CI jobs or automated pipelines, run with `--headless` to print a clean terminal snapshot and immediately exit with code `0`:

```bash
uv run spec-ops monitor live --headless
```

Output:
```text
╭───────────────────────────────────────────────────╮
│ ⚡ SpecOps Live Monitor  |  Tabs: [1: Workers]   │
╰───────────────────────────────────────────────────╯
╭──────── Active Worker Fleet (CPU: 12.4% | Mem: 45.2%) ────────╮
│ Task ID     Worker             PID     Status    Expires     │
│ TASK-0042   spec-ops-worker-1  14022   Active    2026-10-01  │
╰──────────────────────────────────────────────────────────────╯
╭────────────────────── [q] Quit | [r] Refresh ─────────────────╮
╰──────────────────────────────────────────────────────────────╯
```

---

## Emitting Machine-Readable Telemetry

To export the monitor snapshot as structured JSON:

```bash
uv run spec-ops monitor live --json
```
