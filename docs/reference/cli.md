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
