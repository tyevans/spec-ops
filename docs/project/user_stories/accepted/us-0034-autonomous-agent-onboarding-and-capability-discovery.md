---
id: '0034'
title: Autonomous Agent Onboarding and Capability Discovery via AGENTS.md
status: Accepted
created: 2026-09-29
persona: Morgan (The Autonomous Coding Agent)
feature: FEAT-ONB-01
governing_prd: PRD-0001
---

# US-0034 — Autonomous Agent Onboarding and Capability Discovery via AGENTS.md

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** autonomous coding agent,  
**I want** to read a standardized, profile-generated `AGENTS.md` and query agent-specific CLI guidance,  
**So that** I immediately understand all architectural hard invariants, Diataxis documentation requirements, and available CLI tools upon entering the repository.

## Acceptance Criteria

```gherkin
Scenario: Agent Constitution Ingestion and Command Discovery
Given a freshly cloned repository governed by SpecOps
When an autonomous agent inspects "AGENTS.md" at the repository root
Then the agent discovers the 8 Hard Invariants including <500 line limits and blackbox testing
And the agent discovers the mandatory Diataxis documentation integrity requirements
And when the agent runs "spec-ops profiles info --json"
Then the CLI returns active architectural profile rules and quality preflight commands in JSON
And the agent confirms all verification requirements before generating any code.
```

## Rationale & Compelling Value
An opinionated, machine-actionable `AGENTS.md` paired with `spec-ops profiles info --json` provides an instant onboarding contract, preventing common agent failures before they happen.
