---
id: '0117'
title: Autonomous Full-Lifecycle SDLC Orchestrator Skill & Multi-Agent Coordination
status: Accepted
created: 2026-09-30
persona: Alex (The Agentic Systems Architect) & Jordan (The AI-Native Engineering Lead)
feature: FEAT-ORCH-01
governing_prd: PRD-0006
---

# US-0117 — Autonomous Full-Lifecycle SDLC Orchestrator Skill & Multi-Agent Coordination

## Governing PRD
- [`PRD-0006: Autonomous Full-Lifecycle SDLC Orchestrator Skill & Multi-Agent Company-in-a-Box`](../../product/accepted/prd-0006-autonomous-full-lifecycle-sdlc-orchestrator-skill.md)

## User Story

**As an** agentic systems architect and AI-native engineering lead,  
**I want** an inline SpecOps SDLC orchestrator skill that coordinates subagents across all lifecycle phases without detached process forks,  
**So that** personas, PRDs, stories, tasks, and implementations are autonomously driven with zero quality degradation, continuous peer-spec consultation, and instant remediation of orchestration failures.

## Acceptance Criteria

```gherkin
Scenario: Loading Inline Orchestrator Skill without Detached Process Forking
  Given an agent session operating in a repository with SpecOps
  When the agent activates the "spec-ops" orchestrator skill
  Then the skill executes inline without spawning unmonitored external detached processes
  And provides CLI primer runbooks and subagent orchestration protocols.
```

```gherkin
Scenario: Multi-Agent SDLC Subagent Delegation and Spec Consultation
  Given an orchestrator agent coordinating a project lifecycle
  When the orchestrator delegates tasks across SDLC phases (personas, stories, PRD, tasks, implementation)
  Then specialized subagents consult existing approved specs in "docs/project/" to guide implementation
  And report execution state back to the lead orchestrator.
```

```gherkin
Scenario: Actionable Orchestration Failure Protocol
  Given an orchestrator executing lifecycle tasks on the SpecOps repository
  When an orchestration failure occurs during subagent coordination
  Then the failure is captured as an actionable high-priority bug in the backlog
  And the orchestrator dispatches remediation to prevent future stalls.
```

```gherkin
Scenario: Automated Scaffolding of the Orchestrator Skill
  Given a project configured for Antigravity or multi-agent platforms
  When running "spec-ops scaffold --agents antigravity"
  Then ".agents/skills/spec-ops/SKILL.md" is generated with complete lifecycle orchestration instructions and CLI references.
```
