---
id: '0042'
title: One-Command Developer Environment Doctor and Workspace Onboarding
status: Accepted
created: 2026-09-29
persona: Riley (The Human IC Developer)
feature: FEAT-DOC-03
governing_prd: PRD-0004
---

# US-0042 — One-Command Developer Environment Doctor and Workspace Onboarding

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As an** new or returning human software engineer setting up a SpecOps-governed repository,  
**I want** to execute `spec-ops doctor` to audit and auto-repair my local development environment (UV workspace, pre-commit hooks, git worktree directory, and linters),  
**So that** I can achieve a green, fully compliant local development setup in under 60 seconds with zero onboarding guesswork.

## Acceptance Criteria

```gherkin
Scenario: Diagnostic audit of local developer tooling and workspace health
Given an engineer has cloned a SpecOps repository
When the engineer executes "spec-ops doctor"
Then the command verifies:
  | Component           | Check                                                  | Status  |
  | UV Package Manager  | UV installed and lockfile synchronized (uv lock --check)| PASS    |
  | Git Worktree Setup  | .worktrees/ directory configured in .gitignore         | PASS    |
  | Pre-Commit Hooks    | Git pre-commit hook active with spec-ops health check  | FAIL    |
  | Line Limit Health   | Zero source files exceed configured limit (<500 lines)  | PASS    |
And the CLI indicates that 1 issue requires resolution.
```

```gherkin
Scenario: Automated repair of missing hooks and configuration
Given the pre-commit hook is uninstalled
When the engineer executes "spec-ops doctor --fix"
Then the command installs the git pre-commit hook
And verifies the complete toolchain
And outputs "Development environment is healthy and ready for active engineering.".
```

## Rationale & Compelling Value
Junior, mid, and senior developers can clone a repo and be fully productive within 1 minute, eliminating 'works on my machine' friction.
