---
id: 0109
title: 'Proof of Concept: Inline Full-Lifecycle SDLC Orchestrator Skill & CLI Primer'
status: Complete
dependencies:
- TASK-0071
- TASK-0014
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0006
- ADR-0007
- ADR-0008
governing_prds:
- PRD-0006
governing_stories:
- US-0117
target_bc: scaffold
branch: inline_agent_skill_poc
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T22:30:02.956293+00:00'
---

# TASK-0109: Proof of Concept: Inline Full-Lifecycle SDLC Orchestrator Skill & CLI Primer

## Summary
Implement the proof-of-concept (POC) inline agent skill for Antigravity and multi-agent systems (`.agents/skills/spec-ops/SKILL.md`), accompanied by a comprehensive CLI primer (`references/cli_primer.md`) and multi-agent lifecycle orchestration protocol (`references/orchestration_protocol.md`). Provide in-session orchestration runbooks that guide an autonomous agent through every phase of the SpecOps lifecycle (Persona maintenance, Living PRDs, BDD User Stories, INVEST Task Slicing, JIT Refinement & DoR, In-Worktree Subagent Implementation & Peer Consultation, and Verification Gates) without detached external subprocess forking. Integrate the orchestrator skill into `spec-ops scaffold` and enforce the orchestration failure dogfooding protocol.

## Problem Statement & Context
Until now, autonomous execution in SpecOps relied primarily on headless detached worker processes (`spec-ops worker`) running external CLI invocations. While effective for isolated unattended background tasks, this model breaks down when human architects or lead agents need an in-session "company in a box" orchestrator that coordinates through all phases of product development with conversational context, subagent delegation, and cross-phase alignment. Furthermore, developers lack a unified primer on how to drive the entire SpecOps toolchain from the CLI. This POC delivers the first version of the inline orchestrator skill, ready for immediate dogfooding.

## User Stories & Scenarios Satisfied
- **US-0117: Autonomous Full-Lifecycle SDLC Orchestrator Skill & Multi-Agent Coordination**
  - *Scenario: Loading Inline Orchestrator Skill without Detached Process Forking*
    - Given an agent session operating in a repository with SpecOps
    - When the agent activates the "spec-ops" orchestrator skill
    - Then the skill executes inline without spawning unmonitored external detached processes
    - And provides CLI primer runbooks and subagent orchestration protocols.
  - *Scenario: Multi-Agent SDLC Subagent Delegation and Spec Consultation*
    - Given an orchestrator agent coordinating a project lifecycle
    - When the orchestrator delegates tasks across SDLC phases (personas, stories, PRD, tasks, implementation)
    - Then specialized subagents consult existing approved specs in "docs/project/" to guide implementation
    - And report execution state back to the lead orchestrator.
  - *Scenario: Actionable Orchestration Failure Protocol*
    - Given an orchestrator executing lifecycle tasks on the SpecOps repository
    - When an orchestration failure occurs during subagent coordination
    - Then the failure is captured as an actionable high-priority bug in the backlog
    - And the orchestrator dispatches remediation to prevent future stalls.
  - *Scenario: Automated Scaffolding of the Orchestrator Skill*
    - Given a project configured for Antigravity or multi-agent platforms
    - When running "spec-ops scaffold --agents antigravity"
    - Then ".agents/skills/spec-ops/SKILL.md" is generated with complete lifecycle orchestration instructions and CLI references.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: All new and modified Python files (`src/spec_ops/scaffold/adapters.py`, `src/spec_ops/scaffold/skill_templates.py`, `src/spec_ops/scaffold/wizard.py`) remain strictly below 400 lines (ADR-0002).
- **Inline Non-Forking Invariant**: The orchestrator skill instructs the agent to run natively within session context, coordinating via native subagents rather than blind CLI background forks.
- **Dogfooding Custom Invariant**: Added to `AGENTS.md` to ensure any orchestration failure is immediately documented as a high-priority bug and remediated.

## Definition of Done (Blackbox Frontdoor TDD)
1. `.agents/skills/spec-ops/SKILL.md` is authored with frontmatter, 7-phase lifecycle runbooks, and subagent delegation protocols.
2. `.agents/skills/spec-ops/references/cli_primer.md` documents every major CLI subcommand with runnable examples.
3. `.agents/skills/spec-ops/references/orchestration_protocol.md` details subagent roles, spec consultation rules, and failure handling.
4. `src/spec_ops/scaffold/adapters.py` includes `.agents/skills/spec-ops/SKILL.md` in `get_antigravity_slash_commands()`, verified by unit and BDD tests.
5. `AGENTS.md` includes the orchestration failure dogfooding protocol.
6. Passes `uv run spec-ops health`, all pytest tests pass, and lockfile is intact.
