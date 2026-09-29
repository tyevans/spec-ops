---
id: '0072'
title: Zero-Dependency Native Git Hook Scaffolding and Autonomous Worktree Guardrails
status: Accepted
created: 2026-09-29
persona: Sasha (The Trust & Security Officer)
feature: FEAT-SCAF-07
governing_prd: PRD-0005
---

# US-0072 — Zero-Dependency Native Git Hook Scaffolding and Autonomous Worktree Guardrails

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As a** trust and security officer,  
**I want** `spec-ops` to scaffold native, zero-dependency git hooks across local repositories and autonomous agent worktrees,  
**So that** critical invariants—such as strict backlog isolation, UV lockfile integrity, and blackbox testing—are enforced at the git hook level even in environments where external pre-commit frameworks are not installed.

## Acceptance Criteria

```gherkin
Scenario: Scaffolding native git pre-commit and pre-push hooks
Given a git repository initialized with SpecOps
When the security officer runs "spec-ops scaffold hooks --native"
Then executable shell scripts are installed directly into ".git/hooks/pre-commit" and ".git/hooks/pre-push"
And the pre-commit hook runs "uv run spec-ops health" verifying file length limits (<500 lines) and staged file invariants
And does not require third-party python pre-commit tooling.
```
```gherkin
Scenario: Enforcing strict backlog isolation on feature branches via hook
Given a developer or agent working on feature branch "feat/TASK-0012"
When the worker attempts to stage and commit modifications to "docs/project/backlog/PRIORITY.md"
Then the native pre-commit hook intercepts the commit
And aborts with exit code 1
And displays "Invariant Violation (ADR-0005): Feature branches are strictly forbidden from modifying docs/project/backlog/. Backlog transitions are managed automatically upon merge to main."
```
```gherkin
Scenario: Propagating hooks automatically to autonomous worker worktrees
Given an autonomous task execution dispatched via "spec-ops worker --task TASK-0020"
When the worker engine provisions an isolated git worktree at ".worktrees/TASK-0020"
Then the hook scaffolder ensures ".git/worktrees/TASK-0020/hooks" or shared git hooks remain active in the worktree
And blocks the autonomous agent from committing backdoor mocks or invalid lockfiles before creating a pull request.
```

## Rationale & Compelling Value
Hardens the SDLC frontdoors at the git transport layer, guaranteeing that zero code violating hard invariants or security baselines can ever be committed, even by runaway agents.

---
