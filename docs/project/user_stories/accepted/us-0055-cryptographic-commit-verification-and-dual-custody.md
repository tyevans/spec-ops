---
id: '0055'
title: Cryptographic Commit Verification and Dual-Custody Human Sign-Off Gate
status: Accepted
created: 2026-09-29
persona: Sasha (The Trust & Security Officer)
feature: FEAT-SEC-05
governing_prd: PRD-0001
---

# US-0055 — Cryptographic Commit Verification and Dual-Custody Human Sign-Off Gate

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** trust and security officer,  
**I want** SpecOps to verify cryptographic git commit signatures and require dual-custody human sign-offs before any task branch can be marked complete and merged to `main`,  
**So that** every line of agent-generated code merged into the production trunk has provable, verified human authorship or authorization.

## Acceptance Criteria

```gherkin
Scenario: Blocking integration of unsigned git commits into main
Given a project configured with "[security.compliance] require_signed_commits = true"
When "spec-ops queue complete <task-id>" or worker squash-merge is executed on a branch with unsigned commits
Then the command aborts with returncode 1
And outputs "Compliance Violation: Commit lacks valid cryptographic signature (GPG/SSH)".
```

```gherkin
Scenario: Enforcing dual-custody human review sign-off
Given an autonomous agent has passed all preflight checks on a feature branch
When the agent attempts to finalize the task without human approval
Then SpecOps blocks task transition to "complete/"
And requires an authorized human reviewer to execute "spec-ops review sign <task-id> --identity <key-id>"
And once signed, task frontmatter records "signed_off_by: <reviewer>" and the task merges cleanly.
```

## Rationale & Compelling Value
Directly satisfies SOC2 Type II (CC8.1) and ISO 27001 (A.12.1.2) controls requiring dual-custody human authorization before production integration.
