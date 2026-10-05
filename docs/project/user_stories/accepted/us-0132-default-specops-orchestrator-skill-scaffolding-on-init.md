---
id: '0132'
title: Default SpecOps SDLC Orchestrator Skill Scaffolding on Project Onboarding
status: Accepted
created: 2026-10-04
persona: Alex (The Agentic Systems Architect) & Morgan (The Autonomous Coding Agent)
target_bc: scaffold
feature: FEAT-ORCH-01
governing_prd: PRD-0006
scenarios:
  - Scaffolding the SpecOps SDLC orchestrator skill by default on spec-ops init
  - Scaffolding supporting reference runbooks and primers during onboarding
  - Scaffolding the orchestrator skill during brownfield adoption
---

# US-0132 — Default SpecOps SDLC Orchestrator Skill Scaffolding on Project Onboarding

## Governing PRD
- [`PRD-0006: Autonomous Full-Lifecycle SDLC Orchestrator Skill & Multi-Agent Company-in-a-Box`](../../product/accepted/prd-0006-autonomous-full-lifecycle-sdlc-orchestrator-skill.md)

## User Story

**As an** agentic software architect (Alex) or autonomous coding agent (Morgan),  
**I want** `spec-ops init` (and `spec-ops adopt`) to scaffold `.agents/skills/spec-ops/SKILL.md` and supporting reference runbooks by default without requiring explicit agent adapter flags,  
**So that** any newly initialized or adopted repository is immediately equipped with the autonomous full-lifecycle SDLC orchestrator skill and CLI runbooks out of the box.

## Acceptance Criteria

```gherkin
Scenario: Scaffolding the SpecOps SDLC orchestrator skill by default on spec-ops init
  Given a blank project directory
  When the user runs "spec-ops init --name TestApp" without specifying agent flags
  Then ".agents/skills/spec-ops/SKILL.md" is scaffolded into the repository
  And "specops.toml" is created.
```

```gherkin
Scenario: Scaffolding supporting reference runbooks and primers during onboarding
  Given a blank project directory
  When the user initializes a project via "spec-ops init"
  Then ".agents/skills/spec-ops/references/cli_primer.md" exists
  And ".agents/skills/spec-ops/references/balancing_loop.md" exists
  And ".agents/skills/spec-ops/references/orchestration_protocol.md" exists.
```

```gherkin
Scenario: Scaffolding the orchestrator skill during brownfield adoption
  Given an existing codebase directory
  When the user executes "spec-ops adopt"
  Then ".agents/skills/spec-ops/SKILL.md" is created alongside PMaC governance documents.
```

## Rationale & Compelling Value
Previously, agent skills were only created when an engineer explicitly passed `--agents antigravity` or invoked `spec-ops scaffold skill`. Because the SpecOps orchestrator skill is the foundational operating contract for AI assistants working within a PMaC repository, bundling it by default ensures zero friction and instant agent readiness on day one.
