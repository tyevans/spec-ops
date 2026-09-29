---
id: '0080'
title: Pluggable Agent Runner Templates and Worktree Dry-Run Simulation
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-WORK-01
governing_prd: PRD-0004
---

# US-0080 — Pluggable Agent Runner Templates and Worktree Dry-Run Simulation

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As an** agentic systems architect,
  - **I want** to configure custom agent CLI runner templates with variable interpolation and execute worker tasks in dry-run simulation mode,
  - **So that** I can onboard diverse LLM coding assistants (such as Antigravity, Aider, and Claude Code) and verify task prompts and worktree setup without consuming LLM API tokens or risking accidental repo modifications.

## Acceptance Criteria

```gherkin
Scenario: Configuring Custom Agent Runner with Template Placeholders
Given a SpecOps configuration defining "execution.agent_command" as "aider --message-file {prompt_file} --yes --auto-commits"
And a refined task "TASK-0014" targeting bounded context "worker"
When the worker engine prepares the execution environment for "TASK-0014"
Then the worker interpolates "{prompt_file}" to the absolute path of ".worktrees/task-0014/.task-prompt.md"
And sets environment variables "SPEC_OPS_WORKTREE" and "PWD" to the worktree directory
And constructs the process argument list safely without shell quote mangling.
```
```gherkin
Scenario: Zero-Cost Worktree Dry-Run Simulation
Given a refined task "TASK-0010" in "docs/project/backlog/refined/"
When the user runs "spec-ops worker --task TASK-0010 --dry-run"
Then an isolated worktree is created at ".worktrees/task-0010" on branch "feat/task-0010"
And the task prompt is generated at ".worktrees/task-0010/.task-prompt.md" containing governing ADRs, PRDs, and preflight commands
And no external agent process is spawned
And the worker cleans up the dry-run worktree and reports success without modifying git history on "main".
-
```

## Rationale & Compelling Value
- *Adoption*: Teams utilize diverse LLM tooling; pluggable runner templates eliminate vendor lock-in. Dry-run mode gives architects a safe sandbox to test prompt hydration and worktree mechanics before connecting production API keys.
  - *Regular Usage*: Developers and CI pipelines routinely use `--dry-run` to validate prompt generation, frontmatter parsing, and worktree creation without executing expensive agent loops.
  - *Compelling Value*: Removes setup friction, prevents wasted LLM token spend during onboarding, and protects repository branches from misconfigured agents.

---
