---
id: '0011'
title: Brownfield Codebase Adoption and Anti-Rot Invariant Baseline
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-ADP-01
governing_prd: PRD-0001
---

# US-0011 — Brownfield Codebase Adoption and Anti-Rot Invariant Baseline

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** agentic systems architect,  
**I want** to execute `spec-ops adopt` on an existing brownfield repository,  
**So that** the project receives a structured PMaC directory tree, baseline ADRs, and an actionable file length audit that baselines existing monolithic debt without breaking CI builds.

## Acceptance Criteria

```gherkin
Scenario: Initializing SpecOps in an existing repository with grandfathered file debt
Given an existing git repository containing source files where 3 files exceed 500 lines
When the architect runs "spec-ops adopt --profile core,bdd,ddd --name LegacyService"
Then the directory "docs/project/" is created with adrs, product, user_stories, and backlog structures
And "specops.toml" is generated containing an "invariants.file_limits.grandfathered" list with the 3 violating files
And an "AGENTS.md" constitution is generated at the repository root
And the command exits with code 0 reporting "Adoption complete: 3 legacy files grandfathered into technical debt baseline".
```

```gherkin
Scenario: Enforcing anti-rot invariant against newly created files while respecting grandfathered files
Given a repository initialized via "spec-ops adopt" with 3 grandfathered legacy files
When a developer adds a new file "src/new_service.py" containing 520 lines
And runs "spec-ops health"
Then the command exits with code 1
And lists "src/new_service.py" as an unexempt file limit violation (>500 lines)
And indicates that the 3 grandfathered files remain tracked debt items.
```

```gherkin
Scenario: Automatically generating proposed refactoring tasks for grandfathered files
Given a repository initialized via "spec-ops adopt" with grandfathered files
When the architect inspects "docs/project/backlog/proposed/"
Then proposed tasks prefixed with "TASK-REFACTOR-" are generated for each grandfathered file
And each task cites ADR-0002 and identifies the target submodule decomposition path.
```

## Rationale & Compelling Value
Enterprise teams cannot adopt tools that break CI on day one. By providing `spec-ops adopt`, Alex can onboard brownfield services immediately, freezing legacy debt in `specops.toml` while preventing new monolithic file rot.
