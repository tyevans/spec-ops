# CLI Reference

SpecOps provides a unified command-line interface (`spec-ops`).

---

## Subcommands

| Command | Arguments | Description |
|---|---|---|
| `spec-ops init` | `[path] [--name NAME] [--profile PROFILES]` | Bootstrap a new PMaC project |
| `spec-ops profiles list` | None | List available architectural profiles |
| `spec-ops health` | `[path]` | Verify file length limits and PRIORITY sync |
| `spec-ops stats` | `[path]` | Report project statistics and entity counts |
| `spec-ops prd audit` | `[path]` | Audit PRD lifecycle statuses |
| `spec-ops prd decompose` | `<PRD_ID> [--spikes]` | Decompose PRD into vertical slices |
| `spec-ops curate` | `[path]` | Promote unblocked tasks to refined buffer |
| `spec-ops visualizer` | `[--serve] [--build OUT] [--port PORT]` | Interactive 2D graph visualizer |
| `spec-ops worker` | `[--task TASK_ID] [--dry-run] [--no-merge]` | Execute backlog task in isolated worktree |
| `spec-ops cycle` | `[--max-tasks N] [--dry-run] [--build-docs]` | Run end-to-end autonomous development cycle |
| `spec-ops rescue` | `[TASK_ID] [--list] [--complete] [--discard]` | Inspect and recover stalled or failed autonomous worktrees |
