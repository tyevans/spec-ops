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
| `spec-ops prd new` | `[--title TITLE] [--persona PERSONA] [--component COMPONENT] [--friction FRICTION] [--good GOOD] [--anti-goals ANTI_GOALS] [--outcomes OUTCOMES] [--non-interactive]` | Interactively scaffold a new PRD specification in idea stage |
| `spec-ops prd lint` | `[PATH]` | Lint PRD markdown files for mandatory sections and falsifiable outcomes |
| `spec-ops prd promote` | `<PRD_ID> --stage STAGE` | Advance PRD through lifecycle stage gates |
| `spec-ops prd ship` | `<PRD_ID>` | Transition accepted PRD to shipped upon backlog completion |
| `spec-ops prd audit` | None | Audit PRD lifecycle statuses |
| `spec-ops prd decompose` | `<PRD_ID> [--no-spike] [--by-outcomes] [--diff]` | Decompose PRD into vertical slices |
| `spec-ops curate` | `[--infer] [--dry-run] [--model MODEL]` | Perform JIT backlog refinement, cognitive drift reconciliation, and scope slicing |
| `spec-ops visualizer` | `[--serve] [--build OUT] [--port PORT]` | Interactive 2D graph visualizer |
| `spec-ops worker` | `[--task TASK_ID] [--drain] [--max-concurrency N] [--max-tasks M] [--dry-run] [--no-merge] [--no-review] [--skip-review]` | Execute backlog task in isolated worktree with concurrent review |
| `spec-ops cycle` | `[--max-tasks N] [--max-concurrency N] [--drain] [--dry-run] [--no-merge] [--build-docs] [--no-review] [--skip-review]` | Run end-to-end autonomous development cycle |
| `spec-ops rescue` | `[TASK_ID] [--list] [--complete] [--discard] [--prune]` | Inspect and recover stalled or failed autonomous worktrees |
| `spec-ops spike start` | `<SPIKE_ID> [--hypothesis HYPOTHESIS] [--timebox TIMEBOX]` | Instantiate disposable sandboxed spike worktree |
| `spec-ops spike check` | `[SPIKE_ID] [--elapsed ELAPSED]` | Check spike timebox and write isolation |
| `spec-ops spike preflight` | `[SPIKE_ID]` | Enforce in-worktree write isolation preflight hook |
| `spec-ops spike graduate` | `<SPIKE_ID> --result {proven,disproven} [--title TITLE] [--notes NOTES] [--findings FINDINGS]` | Graduate empirical spike findings into an Architectural Decision Record |
| `spec-ops tui` | `[--once] [--view {overview,backlog,tree,health}]` | Launch interactive Terminal UI (TUI) dashboard |
| `spec-ops queue complete` | `<TASK_ID> [--base BASE]` | Gate and complete task integration under merge lock |
| `spec-ops spike start` | `<SPIKE_ID> [--hypothesis HYPOTHESIS] [--timebox TIMEBOX]` | Instantiate disposable sandboxed spike worktree |
| `spec-ops spike check` | `[SPIKE_ID] [--elapsed ELAPSED]` | Check spike timebox and write isolation |
| `spec-ops spike preflight` | `[SPIKE_ID]` | Enforce in-worktree write isolation preflight hook |
| `spec-ops spike graduate` | `<SPIKE_ID> --result {proven,disproven} [--title TITLE] [--notes NOTES] [--findings FINDINGS] [--status STATUS]` | Graduate empirical spike findings into an Architectural Decision Record |
| `spec-ops security verify-lock` | `[--path PATH]` | Verify supply-chain lockfile cryptographic hashes and pinning |
| `spec-ops audit dependencies` | `[--path PATH] [--offline]` | Scan direct and transitive dependencies for High/Critical CVEs and enforce license allowlists |
| `spec-ops docs build` | `[--out OUT_DIR] [--base-url BASE_URL]` | Compile Diataxis documentation static site and embedded 2D visualizer |
| `spec-ops docs audit` | `[--dir DIR] [--strict]` | Audit Diataxis quadrant structure, CLI drift, and documentation code snippets |

