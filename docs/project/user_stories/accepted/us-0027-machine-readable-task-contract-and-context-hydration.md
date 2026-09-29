---
id: '0027'
title: Machine-Readable Task Contract and Architectural Context Hydration
status: Accepted
created: 2026-09-29
persona: Morgan (The Autonomous Coding Agent)
feature: FEAT-AGT-02
governing_prd: PRD-0001
---

# US-0027 — Machine-Readable Task Contract and Architectural Context Hydration

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** autonomous coding agent,  
**I want** SpecOps to automatically compile an unambiguous task contract into `.task-prompt.md` containing governing ADRs, bounded context boundaries, Definition of Ready (DoR) criteria, and exact preflight commands,  
**So that** I understand all architectural constraints and acceptance criteria immediately upon entering a worktree without hallucinating conventions or missing quality gates.

## Acceptance Criteria

```gherkin
Scenario: Hydrating Task Contract into Worktree Environment
Given a refined backlog task "TASK-0012" with target bounded context "core"
And the task cites governing ADRs "ADR-0002, ADR-0003" and acceptance criteria from "US-0002"
When the worker engine initializes the worktree for "TASK-0012"
Then a ".task-prompt.md" file is generated at the worktree root
And the prompt explicitly specifies the 500-line file length limit invariant
And the prompt specifies blackbox frontdoor verification rules with zero private mocks
And the prompt injects the exact preflight command chain "uv lock --check && uv run pytest && uv run spec-ops health"
And the prompt instructs the agent that "docs/project/backlog/" must not be modified on feature branches.
```

## Rationale & Compelling Value
Eliminates cold-start hallucination and guarantees that agent code conforms to repository quality standards from the very first token generated.
