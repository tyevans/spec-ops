# How to Monitor Autonomous Worker Fleet Telemetry and Worktree Operations

This guide demonstrates how to monitor concurrent autonomous AI coding agent worker fleets, inspect active git worktree allocations, track preflight execution stages, and identify stalled tasks requiring human takeover using SpecOps telemetry commands.

---

## 1. Inspecting Live Worker Fleet Telemetry

To view a real-time console table of all active, stalled, and completed autonomous worker processes:

```bash
uv run spec-ops worker --telemetry
```

This aggregates state across all worktrees in `.worktrees/task-*` and outputs an operational dashboard:

```text
                    SpecOps Worker Fleet Telemetry (SpecOps)                    
┏━━━━━┳━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━┳━━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Task┃ Worktree         ┃ Branch       ┃ Status     ┃ Retry ┃ Preflight Hook┃ Elapsed ┃ Memory   ┃ Rescue Command              ┃
┃ ID  ┃ Directory        ┃              ┃            ┃       ┃               ┃         ┃          ┃                             ┃
┡━━━━━╇━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━╇━━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ 0084│ .worktrees/0084  │ feat/task-0084│ Executing │ 1/3   │ uv run pytest │ 45s     │ 128.0 MB │ spec-ops rescue TASK-0084   │
│ 0101│ .worktrees/0101  │ feat/task-0101│ Stalled    │ 3/3   │ File limit    │ 4m 30s  │ 128.0 MB │ spec-ops rescue TASK-0101   │
└─────┴──────────────────┴──────────────┴────────────┴───────┴───────────────┴─────────┴──────────┴─────────────────────────────┘
Total: 2 | Active: 1 | Stalled: 1 | Rescued: 0 | Completed: 0 | Memory: 256.0 MB
⚠️  Alert: 1 worker(s) stalled: TASK-0101
Run 'spec-ops rescue <task-id>' to take over.
```

### Key Metrics Monitored

- **Task ID**: Backlog identifier currently claimed by the worker.
- **Worktree Directory**: Dedicated isolated worktree path on disk.
- **Branch**: Feature branch isolated from `main`.
- **Status**: Live lifecycle stage (`Executing`, `Stalled: Human Takeover Required`, `Healed`).
- **Retries**: Count of retry or self-healing loops consumed out of maximum permitted (e.g. `1/3`).
- **Preflight Hook**: Currently executing quality gate or invariant check (e.g. `File length limit`, `uv run pytest`, `spec-ops health`).
- **Elapsed**: Total run time elapsed in current execution attempt.
- **Memory**: Resident memory footprint of the worker process tree.
- **Rescue Command**: Copy-pasteable takeover command for human escalation.

---

## 2. Structured JSON Output for CI and Monitoring

To export machine-readable telemetry data for external monitoring systems, Prometheus scrapers, or CI pipelines:

```bash
uv run spec-ops worker --telemetry --json
```

Example JSON payload:

```json
{
  "total": 2,
  "active": 1,
  "stalled": 1,
  "rescued": 0,
  "completed": 0,
  "total_memory_mb": 256.0,
  "stalled_tasks": [
    "TASK-0101"
  ],
  "workers": [
    {
      "task_id": "TASK-0084",
      "worktree_path": "/home/ty/workspace/spec-ops/.worktrees/task-0084",
      "branch": "feat/task-0084",
      "status": "Executing",
      "retries": "1/3",
      "current_preflight_hook": "uv run pytest",
      "elapsed_runtime": "45s",
      "memory_usage": "128.0 MB",
      "rescue_cmd": "spec-ops rescue TASK-0084"
    }
  ]
}
```

---

## 3. Responding to Stalled Worker Alerts

When a worker exceeds maximum retry attempts or stalls on a failing preflight gate:

1. **Alert Notification**: Telemetry surfaces an alert banner highlighting the stalled task ID.
2. **Execute Rescue**: Follow the suggested rescue command:
   ```bash
   uv run spec-ops rescue TASK-0101
   ```
3. **Investigate & Repair**: The preserved worktree contains diagnostic logs (`.failure.log`, test outputs) for immediate human troubleshooting.
4. **Complete or Reset**:
   ```bash
   # If repaired: complete and merge
   uv run spec-ops rescue TASK-0101 --complete

   # If unrecoverable: safely discard with failure memory
   uv run spec-ops rescue TASK-0101 --discard
   ```

---

## 4. Visualizer Console Integration

Fleet telemetry is also streamed live to the SpecOps interactive Web Visualizer dashboard. Open the visualizer to view graphical execution telemetry alongside the relational knowledge graph:

```bash
uv run spec-ops visualizer --serve
```

Navigate to the **Operations & Fleet Telemetry** tab to inspect worker nodes, active git branches, and resource consumption in real time.
