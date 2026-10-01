# How to Orchestrate the SpecOps SDLC with the Inline Agent Skill

This guide explains how to use the SpecOps inline orchestrator skill (`.agents/skills/spec-ops/SKILL.md`) to run the entire project lifecycle—from personas and living PRDs down to verified pull requests—using autonomous subagents without detached process forks.

---

## 1. Overview & Setup

The SpecOps skill turns an AI coding assistant into a **Lead SDLC Orchestrator** ("Company in a Box"). Unlike legacy workers that spawn detached external shell processes, the inline orchestrator operates directly in the active agent session, delegating tasks to specialized subagents while retaining full visibility, interactive steering, and conversational context.

### Scaffolding Universal Multi-Platform Skills

To package and scaffold the universal orchestrator skill across platforms:

```bash
# Scaffold for all supported platforms (Antigravity, Claude Code, Cursor)
uv run spec-ops scaffold skill --target all

# Or scaffold for a specific platform
uv run spec-ops scaffold skill --target antigravity
```

This scaffolds:
- **Antigravity**: `.agents/skills/spec-ops/SKILL.md` and complete reference runbooks in `.agents/skills/spec-ops/references/` (`cli_primer.md`, `balancing_loop.md`, `orchestration_protocol.md`).
- **Claude Code**: `CLAUDE.md`, `.claude/skills/spec-ops/SKILL.md`, `.claude/skills/spec-ops/references/`, and `.claude/commands/spec-ops.md`.
- **Cursor**: `.cursorrules`, `.cursor/rules/spec-ops.mdc`, and `.cursor/rules/references/`.


---

## 2. Triggering the Skill

In Antigravity or compatible assistants, trigger the skill via slash command or naturally in conversation:

```text
/spec-ops
```
Or:
```text
"Run the SpecOps lifecycle for the next feature milestone."
```

---

## 3. The 7-Phase Lifecycle

The skill guides the agent through seven distinct phases:

1. **Persona Discovery & Maintenance**: Audits `docs/project/user_stories/PERSONAS.md` to ensure emerging archetypes and evolving user pain points are captured.
2. **Product Discovery & Living PRDs**: Crafts or updates PRDs under `docs/project/product/accepted/`, validating with `uv run spec-ops prd lint`.
3. **Multi-Faceted BDD User Stories**: Scaffolds executable Gherkin stories in `docs/project/user_stories/accepted/`, linked to personas and bounded contexts.
4. **INVEST Task Slicing**: Slices scopes into thin vertical slices (<500 lines per file) and architectural spikes (`SPIKE-XXXX`).
5. **JIT Refinement & Definition of Ready**: Runs `uv run spec-ops curate --infer` to reconcile architectural drift and populate the ~10 task ready buffer in `refined/`.
6. **Subagent In-Worktree Implementation**: Dispatches `implementation-agent` into isolated worktrees (`uv run spec-ops worktree create TASK-XXXX`), consulting peer agents and approved specs before modifying code.
7. **Verification & Integration Gates**: Runs `uv run spec-ops health`, `uv run pytest`, and `uv lock --check` before merging to `main` and completing the task.

---

## 4. Orchestration Failure Dogfooding Protocol

When operating on the SpecOps repository itself, any orchestration failure (e.g. stalled subagent, test timeout, tool error) is an **actionable task**:

1. **Record the Failure**: Immediately document the failure as a high-priority bug in `docs/project/backlog/proposed/`.
2. **Remediate**: Dispatch a subagent to resolve the root cause and improve developer ergonomics for future runs.
