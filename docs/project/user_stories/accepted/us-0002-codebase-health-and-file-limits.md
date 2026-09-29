---
id: '0002'
title: Codebase Invariant Health and File Length Limit Verification
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-HLT-01
governing_prd: PRD-0001
---

# US-0002 — Codebase Invariant Health and File Length Limit Verification

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** engineering lead,  
**I want** to run `spec-ops health` in CI and local preflights,  
**So that** no source files exceed 500 lines and the backlog index remains 100% synchronized with disk state.

## Acceptance Criteria

### Scenario 1: Clean Repository Verification
```gherkin
Given a repository where all source files contain fewer than 500 lines
And PRIORITY.md accurately indexes all tasks across complete, refined, and proposed directories
When the developer runs "spec-ops health"
Then the command exits with code 0
And reports "Invariant Met: Zero source files exceed length limit".
```

### Scenario 2: Blocking Monolithic Regressions
```gherkin
Given a source file that expands beyond 500 lines
When the preflight command runs "spec-ops health"
Then the command exits with code 1
And lists the violating file path, exact line count, and configured limit.
```
