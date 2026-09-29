---
id: '0053'
title: Immutable Supply-Chain Lockfile Verification and Slopsquatting Defense
status: Accepted
created: 2026-09-29
persona: Sasha (The Trust & Security Officer)
feature: FEAT-SEC-03
governing_prd: PRD-0002
---

# US-0053 — Immutable Supply-Chain Lockfile Verification and Slopsquatting Defense

## Governing PRD
- [`PRD-0002: Enterprise Security, Supply-Chain & Compliance Engine`](../../product/accepted/prd-0002-enterprise-security-supply-chain-and-compliance-engine.md)

## User Story

**As an** trust and security officer,  
**I want** SpecOps to enforce strict dependency lockfile immutability and block unauthorized third-party package modifications in agent worktrees,  
**So that** autonomous agents cannot introduce hallucinated, typosquatted, or unvetted external packages (slopsquatting) into the dependency tree.

## Acceptance Criteria

```gherkin
Scenario: Rejecting unauthorized dependency additions in task worktrees
Given a backlog task whose frontmatter does not declare "allows_dependencies: true"
When an autonomous coding agent modifies "pyproject.toml" or "uv.lock" to add an unapproved package
Then "spec-ops worker" preflight detects the unauthorized lockfile alteration
And the worker halts execution with an "Unauthorized Dependency Modification" violation
And the task is flagged for human triage and not merged into "main".
```

```gherkin
Scenario: Cryptographic hash verification for authorized dependency tasks
Given a backlog task with "allows_dependencies: true" explicitly approved in frontmatter
When the worker updates dependencies
Then "uv lock --check" executes to verify all package hashes match upstream cryptographic hashes
And any untrusted or unpinned package causes preflight to fail with returncode 1.
```

## Rationale & Compelling Value
'Slopsquatting' is an emerging vector in autonomous development. Strict lockfile gating completely insulates the codebase from hallucinated dependency attacks.
