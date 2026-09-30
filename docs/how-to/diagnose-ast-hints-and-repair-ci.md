# How-To: Diagnose AST Hints and Repair Remote CI Failures

This guide shows how SpecOps autonomous worker streams utilize targeted AST diagnostic hint injection, enforce empty-diff guardrails, and execute automated remote CI repair loops.

---

## 1. Targeted AST Diagnostic Hint Injection

When a worker experiences preflight test failures or lint regressions, SpecOps analyzes the Python AST of failing test files and error tracebacks to generate structured repair prompts:

```bash
spec-ops worker execute TASK-0047 --dry-run
```

Key capabilities:
- **Seam Extraction**: Extracts function definitions, class interfaces, and import seams directly from the AST without relying on fragile regex matching.
- **Context Pruning**: Filters unrelated implementation details to keep the repair context focused and prevent LLM context saturation.
- **Actionable Assertions**: Surfaces failing assertion statements alongside expected vs. actual values directly in `.task-prompt.md`.

---

## 2. Empty-Diff Guardrails

To prevent autonomous coding agents from claiming false task completion when no meaningful code changes were produced, SpecOps enforces strict empty-diff guardrails:

- **Cosmetic Modification Rejection**: Pure whitespace changes or empty commits are immediately rejected.
- **Scratch File Isolation**: Changes to ephemeral worker prompts (`.task-prompt.md`, `.failure.log`) are ignored when determining if functional progress occurred.
- **Fail-Fast Exit**: If an agent finishes without producing code modifications, the worktree is preserved for human triage and the task remains in the ready queue.

---

## 3. Remote CI Failure Ingestion and Repair

When a remote CI pipeline run fails (e.g. in GitHub Actions or GitLab CI), engineers or automated orchestrators can ingest the CI failure and trigger an autonomous repair loop:

```bash
spec-ops worker ci-heal --task TASK-0047
```

The repair loop executes the following steps:
1. **Traceback Parsing**: Extracts failing step names, file paths, line numbers, and Python exception types.
2. **Repair Prompt Synthesis**: Injects the failure context and AST hints into `.task-prompt.md`.
3. **Targeted Re-execution**: Dispatches the assigned agent to resolve the specific regression.
4. **Preflight Verification**: Re-runs `uv run pytest` and `uv run spec-ops health` locally before permitting re-submission to remote CI.
