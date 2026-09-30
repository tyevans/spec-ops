---
id: '0006'
title: Autonomous Full-Lifecycle SDLC Orchestrator Skill & Multi-Agent Company-in-a-Box
status: Accepted
created: 2026-09-30
target_persona: Alex (The Agentic Systems Architect) & Jordan (The AI-Native Engineering Lead)
component: core
---

# PRD-0006 — Autonomous Full-Lifecycle SDLC Orchestrator Skill & Multi-Agent Company-in-a-Box

## Who this is for

- **Alex (The Agentic Systems Architect)**: Wants an end-to-end autonomous orchestrator that guides agents through version-locked PMaC specifications without losing context or violating invariants.
- **Jordan (The AI-Native Engineering Lead)**: Wants a "company in a box" orchestrator that coordinates personas, stories, PRDs, task refinement, and multi-agent implementation with zero quality degradation.
- **Morgan (The Autonomous Coding Agent)**: Needs an inline skill (no blind detached subprocess forks) that provides a clear primer on the CLI and orchestrates specialized subagents via native agent tools.

## What the person cannot do today

- **Disconnected SDLC Phases**: Agents operate on isolated tasks without continuous understanding of personas, PRDs, and cross-cutting architectural constraints.
- **Detached Subprocess Blind Spots**: Traditional external worker runners fork background processes that leave the primary interactive agent blind and unable to steer or consult in real-time.
- **Stale or Forgotten Specifications**: Personas and PRDs rot because no autonomous engine maintains them continuously alongside code changes.
- **Ad-Hoc Tooling Knowledge**: New agents and developers struggle to navigate the extensive SpecOps CLI commands across all stages of project delivery.

## What good looks like

1. **Inline Skill Architecture (No Fork)**:
   - Runs directly within the primary agent session, leveraging native subagent tools (`invoke_subagent`, `send_message`, `manage_subagents`) for parallel task delegation while keeping the lead orchestrator informed.
2. **Comprehensive CLI Primer**:
   - Provides instant runnable guidance across the full SpecOps CLI lifecycle (`init`, `adopt`, `health`, `prd`, `curate`, `task`, `worker`, `worktree`, `queue`, `rescue`, `test`, `verify`, `docs`, `release`, `report`).
3. **End-to-End SDLC Phase Protocols**:
   - Explicit procedural runbooks for:
     - Persona Discovery & Maintenance (`PERSONAS.md`)
     - Living PRD Formulation & Falsifiable Linting (`docs/project/product/`)
     - Multi-Faceted User Story Mapping (`docs/project/user_stories/`)
     - INVEST Task Decomposition & Slicing (`docs/project/backlog/proposed/`)
     - JIT Backlog Curation & DoR Gatekeeping (`docs/project/backlog/refined/`, `spec-ops curate --infer`)
     - Multi-Agent In-Worktree Implementation & Peer Consultation
     - Verification, Preflight & PR Integration Gates (`spec-ops health`, `uv run pytest`, `uv lock --check`)
4. **Orchestration Failure Dogfooding Invariant**:
   - Any orchestration failure encountered during project execution is treated as an actionable task/bug and remediated immediately.
5. **Universal Distribution**:
   - Packaged for Antigravity `.agents/skills/`, Claude Code, Cursor, and scaffolded into new/existing projects via `spec-ops scaffold`.

## What this does not do

- It does not bypass human architectural review or dual-custody gates for production releases.
- It does not allow unverified, hallucinated code to bypass blackbox frontdoor verification or file length limits (<500 lines).

## Checkable Outcomes

1. An inline skill `.agents/skills/spec-ops/SKILL.md` is present and recognized by the agent platform with executable CLI runbooks and subagent orchestration protocols.
2. Scaffolding SpecOps agent adapters (`spec-ops scaffold --agents antigravity`) generates `.agents/skills/spec-ops/SKILL.md`.
3. The skill includes a standalone CLI primer and protocol documentation in `references/`.
4. Subagent orchestration guidelines explicitly specify how subagents consult each other and existing approved specs (`docs/project/`).
5. Definition of Ready and Definition of Done checks are rigorously embedded into the orchestration lifecycle.

## Linked User Stories

- `US-0117`
