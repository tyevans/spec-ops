---
id: '0007'
title: Agent Constitution and Invariant Instructions Scaffolding (AGENTS.md)
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-AGT-01
governing_prd: PRD-0001
---

# US-0007 — Agent Constitution and Invariant Instructions Scaffolding (AGENTS.md)

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** agentic systems architect,  
**I want** `spec-ops init` to scaffold an opinionated `AGENTS.md` file dynamically constructed from the selected architectural profiles,  
**So that** autonomous coding assistants (Antigravity, Claude, Cursor, Aider) entering the repository immediately inherit non-negotiable hard invariants, backlog navigation protocols, Diataxis documentation rules, and test-driven development workflows.

## Acceptance Criteria

### Scenario 1: Generating Profile-Driven AGENTS.md
```gherkin
Given a project initialized with profiles "core,bdd,ddd"
When the developer runs "spec-ops init"
Then an "AGENTS.md" file is generated at the repository root
And the Hard Invariants section includes the baseline ADR laws (file limits <500 lines, blackbox verification, worktree isolation)
And the Navigation section links to "docs/project/README.md" and backlog directories.
```
