---
id: '0113'
title: Cryptographic Commit Verification and Dual-Custody Human Sign-Off Gate
status: Accepted
created: 2026-09-29
persona: Sasha (The Trust & Security Officer)
feature: FEAT-SEC-06
governing_prd: PRD-0002
---

# US-0113 — Cryptographic Commit Verification and Dual-Custody Human Sign-Off Gate

## Governing PRD
- [`PRD-0002: Enterprise Security, Supply-Chain & Compliance Engine`](../../product/accepted/prd-0002-enterprise-security-supply-chain-and-compliance-engine.md)

## User Story

**As a** trust and security officer (Sasha),
  - **I want** SpecOps to verify cryptographic signatures (GPG/SSH) on all git commits and mandate dual-custody human sign-offs before any agent-authored task branch can be marked complete and merged to `main`,
  - **So that** every line of agent-generated code merged into the production trunk has provable, verified human authorship or authorization.

## Acceptance Criteria

```gherkin
Scenario: Blocking integration of unsigned git commits into main
Given a project configured with "[security.compliance] require_signed_commits = true"
When "spec-ops queue complete <task-id>" or worker squash-merge is executed on a branch with unsigned commits
Then the command aborts with returncode 1
And outputs "Compliance Violation: Commit <commit-sha> lacks valid cryptographic signature (GPG/SSH)".
```
```gherkin
Scenario: Enforcing dual-custody human review sign-off on autonomous agent tasks
Given an autonomous agent has passed all preflight checks on a feature branch for task "TASK-0042"
When the agent attempts to finalize and merge the task via "spec-ops queue complete TASK-0042"
Then SpecOps blocks the task transition to "complete/"
And outputs "Dual-Custody Gate: Autonomous agent task requires verified human review sign-off. Run 'spec-ops review sign TASK-0042 --identity <key-id>'".
```
```gherkin
Scenario: Recording verified human reviewer signature into task metadata and git commit
Given an authorized human reviewer executes "spec-ops review sign TASK-0042 --identity 'Riley <riley@example.com>'"
When the cryptographic signature is verified against the authorized signers keyring
Then task frontmatter records "signed_off_by: 'Riley <riley@example.com>'" and sign-off timestamp
And subsequent execution of "spec-ops queue complete TASK-0042" merges cleanly to "main" with the structured "SpecOps-Signed-By" git trailer.
-
```

## Rationale & Compelling Value
- **Enterprise Adoption**: Leverages native Git signing mechanisms (`git config commit.gpgsign true` and `.ssh/allowed_signers`), integrating seamlessly with GitHub/GitLab branch protection rules without external identity providers.
  - **Regular Usage**: Enforced at the merge lock integration boundary (`spec-ops queue complete <task-id>`) whenever transitioning tasks from `refined/` to `complete/`.
  - **Compelling Value**: Satisfies strict compliance mandates including SOC2 Type II (CC8.1 Change Authorization), ISO 27001 (A.12.1.2 Change Management), and PCI-DSS (Req 6.4.5 Dual Control), ensuring no AI agent can push code directly into production trunks without accountable human authorization.

---
