---
id: '0111'
title: Immutable Supply-Chain Lockfile Verification and Slopsquatting Defense
status: Accepted
created: 2026-09-29
persona: Sasha (The Trust & Security Officer)
feature: FEAT-SEC-04
governing_prd: PRD-0002
---

# US-0111 — Immutable Supply-Chain Lockfile Verification and Slopsquatting Defense

## Governing PRD
- [`PRD-0002: Enterprise Security, Supply-Chain & Compliance Engine`](../../product/accepted/prd-0002-enterprise-security-supply-chain-and-compliance-engine.md)

## User Story

**As a** trust and security officer (Sasha),
  - **I want** SpecOps to enforce strict dependency lockfile immutability and verify cryptographic package hashes via `uv lock --check`, blocking unauthorized package additions in task worktrees,
  - **So that** autonomous agents cannot introduce hallucinated packages ("slopsquatting"), typosquatted dependencies, or unvetted external libraries into the dependency tree.

## Acceptance Criteria

```gherkin
Scenario: Rejecting unauthorized dependency additions in task worktrees
Given a backlog task whose frontmatter does not declare "allows_dependencies: true"
When an autonomous coding agent modifies "pyproject.toml" or "uv.lock" to add an unapproved package
Then "spec-ops worker" preflight detects the unauthorized lockfile alteration
And the worker halts execution with an "Unauthorized Dependency Modification" violation
And the task is flagged for human triage and blocked from merging into "main".
```
```gherkin
Scenario: Cryptographic hash verification for authorized dependency tasks
Given a backlog task with "allows_dependencies: true" explicitly approved in its frontmatter
When the worker updates dependencies and executes preflight verification
Then "uv lock --check" executes to verify all package hashes match upstream cryptographic hashes
And any untrusted, unpinned, or drifted package causes preflight to fail with returncode 1.
```
```gherkin
Scenario: Integration gate verifies lockfile immutability across the branch diff
Given an autonomous feature branch submitted for completion
When the orchestrator executes "spec-ops queue complete <task-id>" under merge lock
Then the engine verifies that the branch diff against "main" contains zero unstaged or unapproved lockfile alterations
And passes only when lockfile integrity is cryptographically validated.
-
```

## Rationale & Compelling Value
- **Enterprise Adoption**: Standardized on Python UV workspaces (Hard Invariant 4). Eliminates chaotic virtual environments and bare `pip` invocations.
  - **Regular Usage**: Enforced during task refinement, in-worktree preflight, and orchestrator merge locking.
  - **Compelling Value**: "Slopsquatting" (attackers publishing malicious packages matching AI hallucinations) is a top emerging threat in autonomous software development. Lockfile immutability by default completely eliminates this attack vector.

---
