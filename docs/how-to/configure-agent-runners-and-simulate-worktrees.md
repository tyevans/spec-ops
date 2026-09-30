# How-To: Configure Pluggable Agent Runners and Simulate Worktree Execution

This guide demonstrates how to configure custom agent execution templates in `specops.toml` and simulate zero-cost worktree runs using `--dry-run`.

---

## Configuring Pluggable Agent Runners

SpecOps supports pluggable agent command templates in `specops.toml` under `[execution]`:

```toml
[execution]
agent_command = "agy --dangerously-skip-permissions -p {prompt}"
agent_max_attempts = 3
git_branch_prefix = "feat/"
backlog_isolation = true
```

### Supported Template Placeholders

When invoking an agent, the command runner safely interpolates the following placeholders into `argv` without shell injection:

| Placeholder | Replaced Value | Example |
|---|---|---|
| `{prompt}` | Raw prompt markdown text payload | `agy -p "{prompt}"` |
| `{prompt_file}` | Absolute path to `.task-prompt.md` | `claude -p {prompt_file}` |
| `{SPEC_OPS_WORKTREE}` | Target isolated worktree directory | `.worktrees/task-0045` |
| `{PWD}` | Target isolated worktree directory | `.worktrees/task-0045` |

---

## Simulating Worktree Execution (`--dry-run`)

To verify task preflight, prompt generation, and worktree scaffolding without invoking an LLM or mutating git commit history:

```bash
spec-ops worker TASK-0045 --dry-run
```

During a dry-run execution:
1. Provisions the isolated git worktree at `.worktrees/task-<id>`.
2. Validates initial preflight checks (`uv lock --check`, `uv run pytest`, `spec-ops health`).
3. Generates `.task-prompt.md` containing all governing ADRs, PRD context, and INVEST criteria.
4. Skips LLM process invocation and git merge commits.
5. Cleans up disposable dry-run artifacts automatically.

---

## Inspecting Machine-Readable Tasks (`--json`)

To inspect task metadata, dependencies, and branch names in automation pipelines or external scripts:

```bash
spec-ops queue next --json
```

Or for health inspection:

```bash
spec-ops health --json
```

Output format adheres to standard JSON schemas for downstream agent orchestrators.
