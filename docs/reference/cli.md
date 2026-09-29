# CLI Reference

SpecOps provides a unified command-line interface (`spec-ops`).

---

## Subcommands

| Command | Arguments | Description |
|---|---|---|
| `spec-ops init` | `[--dir PATH] [--name NAME] [--profile PROFILES] [--agent AGENTS] [--diataxis/--no-diataxis] [--github-pages/--no-github-pages] [--pre-commit/--no-pre-commit]` | Bootstrap a new PMaC project with profile ADRs and multi-agent platform adapters |
| `spec-ops profiles list` | None | List available architectural profiles |
| `spec-ops profiles apply` | `<PROFILE_NAME>` | Apply architectural profile to current repository |
| `spec-ops profiles sync` | `<PROFILE_NAME>` | Synchronize or restore architectural profile artifacts |
| `spec-ops scaffold agents` | None | Regenerate AGENTS.md constitution from installed profiles |
| `spec-ops health` | `[--security]` | Verify file length limits, PRIORITY sync, and security profile guardrails |
| `spec-ops stats` | None | Report project statistics and entity counts |
| `spec-ops prd create` | `[--title TITLE] [--persona PERSONA] [--component COMPONENT] [--summary SUMMARY] [--stage STAGE]` | Scaffold a new PRD specification |
| `spec-ops prd audit` | None | Audit PRD lifecycle statuses |
| `spec-ops prd decompose` | `<PRD_ID> [--no-spike]` | Decompose PRD into vertical slices |
| `spec-ops curate` | None | Promote unblocked tasks to refined buffer |
| `spec-ops visualizer` | `[--serve] [--build OUT] [--port PORT]` | Interactive 2D graph visualizer |
| `spec-ops worker` | `[--task TASK_ID] [--drain] [--max-concurrency N] [--max-tasks M] [--dry-run] [--no-merge] [--no-review] [--skip-review]` | Execute backlog task in isolated worktree with concurrent review |
| `spec-ops cycle` | `[--max-tasks N] [--max-concurrency N] [--drain] [--dry-run] [--no-merge] [--build-docs] [--no-review] [--skip-review]` | Run end-to-end autonomous development cycle |
| `spec-ops rescue` | `[TASK_ID] [--list] [--complete] [--discard] [--prune]` | Inspect and recover stalled or failed autonomous worktrees |
| `spec-ops tui` | `[--once] [--view {overview,backlog,tree,health}]` | Launch interactive Terminal UI (TUI) dashboard |
| `spec-ops docs build` | `[--out OUT_DIR] [--base-url BASE_URL]` | Compile Diataxis documentation static site and embedded 2D visualizer |
| `spec-ops docs audit` | `[--dir DIR] [--strict]` | Audit Diataxis quadrant structure, CLI drift, and documentation code snippets |
