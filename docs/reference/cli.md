# CLI Reference

SpecOps provides a unified command-line interface (`spec-ops`).

---

## Subcommands

| Command | Arguments | Description |
|---|---|---|
| `spec-ops init` | `[--dir PATH] [--name NAME] [--profile PROFILES] [--diataxis/--no-diataxis]` | Bootstrap a new PMaC project |
| `spec-ops profiles list` | None | List available architectural profiles |
| `spec-ops health` | None | Verify file length limits and PRIORITY sync |
| `spec-ops stats` | None | Report project statistics and entity counts |
| `spec-ops prd audit` | None | Audit PRD lifecycle statuses |
| `spec-ops prd decompose` | `<PRD_ID> [--no-spike]` | Decompose PRD into vertical slices |
| `spec-ops curate` | None | Promote unblocked tasks to refined buffer |
| `spec-ops visualizer` | `[--serve] [--build OUT] [--port PORT]` | Interactive 2D graph visualizer |
| `spec-ops worker` | `[--task TASK_ID] [--dry-run] [--no-merge]` | Execute backlog task in isolated worktree |
| `spec-ops cycle` | `[--max-tasks N] [--dry-run] [--no-merge] [--build-docs]` | Run end-to-end autonomous development cycle |
| `spec-ops rescue` | `[TASK_ID] [--list] [--complete] [--discard]` | Inspect and recover stalled or failed autonomous worktrees |
| `spec-ops docs build` | `[--out OUT_DIR] [--base-url BASE_URL]` | Compile Diataxis documentation static site and embedded 2D visualizer |
