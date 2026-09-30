# How to Orchestrate the SpecOps SDLC with the Inline Agent Skill

This guide explains how to use the SpecOps inline orchestrator skill (`.agents/skills/spec-ops/SKILL.md`) to run the entire project lifecycle—from personas and living PRDs down to verified pull requests—using autonomous subagents without detached process forks.

---

## 1. Overview & Setup

The SpecOps skill turns an AI coding assistant into a **Lead SDLC Orchestrator** ("Company in a Box"). Unlike legacy workers that spawn detached external shell processes, the inline orchestrator operates directly in the active agent session, delegating tasks to specialized subagents while retaining full visibility, interactive steering, and conversational context.

### Scaffolding the Skill

To generate the skill in any SpecOps project:

```bash
uv run spec-ops scaffold agents
```

This scaffolds:
- `.agents/skills/spec-ops/SKILL.md` (Main instruction runbook)
- `.agents/skills/spec-ops/references/cli_primer.md` (Full CLI command reference)
- `.agents/skills/spec-ops/references/orchestration_protocol.md` (Multi-agent coordination protocol)

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
