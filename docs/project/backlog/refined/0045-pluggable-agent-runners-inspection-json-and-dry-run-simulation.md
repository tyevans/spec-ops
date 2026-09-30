---
id: '0045'
title: Pluggable Agent Runners, CLI Inspection JSON Output, and Worktree Dry-Run Simulation
status: Refined
created: 2026-09-29
dependencies:
  - TASK-0014
  - TASK-0044
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0007
  - ADR-0008
  - ADR-0009
governing_prds:
  - PRD-0004
governing_stories:
  - US-0080
  - US-0029
  - US-0034
target_bc: worker
---

# TASK-0045: Pluggable Agent Runners, CLI Inspection JSON Output, and Worktree Dry-Run Simulation

## Summary
Implement pluggable agent CLI runner templates with variable interpolation (`{prompt_file}`, env vars `SPEC_OPS_WORKTREE`, `PWD`), worktree dry-run simulation mode (`spec-ops worker --task TASK-XXXX --dry-run`) to verify execution setups without consuming LLM API tokens, machine-readable structured JSON output across all SpecOps inspection commands (`--json`), and programmatic agent onboarding discovery via `AGENTS.md` and `spec-ops profiles info --json`.

## Problem Statement & Context
Engineering teams employ diverse autonomous coding assistants (such as Antigravity, Aider, and Claude Code). Hardcoding invocation semantics introduces vendor lock-in and impedes onboarding. Furthermore, verifying worktree creation, prompt compilation, and environment variables currently requires spawning full agent processes, wasting expensive LLM tokens. Additionally, autonomous agents need structured JSON payloads rather than ANSI terminal strings to parse backlog items, health violations, and profile invariants reliably.

## User Stories & Scenarios Satisfied
- **US-0080: Pluggable Agent Runner Templates and Worktree Dry-Run Simulation**
  - *Scenario: Configuring Custom Agent Runner with Template Placeholders*
    - Given a SpecOps repository configured with a custom runner command template containing "{prompt_file}"
    - When the developer executes "spec-ops worker --task TASK-XXXX --dry-run"
    - Then the system interpolates the absolute path to the generated prompt file into the command invocation.
  - *Scenario: Zero-Cost Worktree Dry-Run Simulation*
    - Given a refined task in "docs/project/backlog/refined/"
    - When an engineer runs "spec-ops worker --task TASK-XXXX --dry-run"
    - Then an isolated worktree is created, preflight checks and prompt generation are simulated, and the worktree is cleanly dismantled without calling external LLM APIs.
- **US-0029: Machine-Readable JSON Output for Autonomous CLI Inspection**
  - *Scenario: Inspecting Next Backlog Task with Machine-Readable JSON*
    - Given ready tasks in the backlog
    - When an autonomous agent executes "spec-ops queue next --json"
    - Then the stdout contains a valid JSON payload with task ID, title, branch name, and prompt metadata.
  - *Scenario: Parsing Health Violations via Structured JSON*
    - Given a repository with file length warnings or backlog issues
    - When an autonomous agent runs "spec-ops health --json"
    - Then the stdout produces structured JSON detailing invariant errors and warning counts without ANSI escape codes.
- **US-0034: Autonomous Agent Onboarding and Capability Discovery via AGENTS.md**
  - *Scenario: Agent Constitution Ingestion and Command Discovery*
    - Given a newly spawned autonomous coding agent
    - When the agent inspects "AGENTS.md" and runs "spec-ops profiles info --json"
    - Then the agent discovers operating rules, CLI entry points, and active architectural invariants.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Pluggable runner execution engine in `src/spec_ops/worker/runners.py` and JSON formatters in `src/spec_ops/cli/formatters.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary CLI template strings and environment maps assert that placeholder interpolation (`{prompt_file}`) and argument list construction prevent shell quote injection, path traversal, or unhandled token errors.
- **Mutmut Mutation Scope**: Core runner template interpolation in `src/spec_ops/worker/runners.py` and JSON serialization logic in `src/spec_ops/cli/formatters.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Configuring custom runner command templates (e.g. `aider --message-file {prompt_file} --yes`) interpolates absolute prompt file paths safely into argv lists without shell mangling.
2. Executing `spec-ops worker --task TASK-XXXX --dry-run` creates the isolated worktree `.worktrees/<task-id>`, compiles `.task-prompt.md`, logs environment settings, verifies configuration, and tears down the worktree cleanly with exit code 0 and zero git history changes.
3. Executing `spec-ops queue next --json`, `spec-ops health --json`, and `spec-ops profiles info --json` outputs pure, valid JSON payloads matching domain schemas without ANSI escape sequences or terminal banners.
4. Autonomous agents reading `AGENTS.md` and querying `spec-ops profiles info --json` receive structured verification and invariant criteria.
5. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
