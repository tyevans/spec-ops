---
id: '0110'
title: Real-Time Secret and High-Entropy Credential Detection in Worktree Diffs
status: Accepted
created: 2026-09-29
persona: Sasha (The Trust & Security Officer)
feature: FEAT-SEC-03
governing_prd: PRD-0002
---

# US-0110 — Real-Time Secret and High-Entropy Credential Detection in Worktree Diffs

## Governing PRD
- [`PRD-0002: Enterprise Security, Supply-Chain & Compliance Engine`](../../product/accepted/prd-0002-enterprise-security-supply-chain-and-compliance-engine.md)

## User Story

**As a** trust and security officer (Sasha),
  - **I want** `spec-ops health --security` and autonomous worker preflight verification to scan unstaged, staged, and branch diffs for exposed credentials, private keys, and high-entropy secrets,
  - **So that** autonomous agents and human developers are physically blocked from committing secrets into version control history before commits are created.

## Acceptance Criteria

```gherkin
Scenario: Blocking commits containing high-entropy secrets or private tokens
Given an autonomous agent worktree where an agent or developer has written an OpenAI API key, AWS secret access key, or RSA private key into a source file
When the worker engine executes "spec-ops health --security" prior to git commit
Then the scanner detects the high-entropy credential pattern
And the preflight check exits with returncode 1, aborting the commit
And diagnostic feedback listing the offending file path, line number, and masked token snippet (e.g., "sk-proj-****4x9Z") is returned to the agent prompt for self-healing remediation.
```
```gherkin
Scenario: Blocking inclusion of unignored sensitive dotfiles in git tracking
Given an autonomous worker session where the agent generates a ".env", ".env.production", or "id_rsa" file
When the worker engine executes preflight verification
Then "spec-ops health --security" flags the presence of unignored sensitive files
And the commit is aborted with actionable instructions to add the file to ".gitignore" and remove it from git staging.
```
```gherkin
Scenario: Clean worktree passes preflight credential scan
Given an autonomous agent worktree with feature modifications referencing credentials strictly through environment variables
When the preflight command "spec-ops health --security" executes
Then the check exits with returncode 0
And reports "Security Invariant Met: 0 credential leaks detected in working tree".
-
```

## Rationale & Compelling Value
- **Enterprise Adoption**: Zero setup or external API required; ships with an optimized rule engine and Shannon entropy calculator detecting standard cloud, SaaS, AI, and cryptographic keys out of the box.
  - **Regular Usage**: Active in pre-commit git hooks, in-worktree worker preflights, and pull request CI validation.
  - **Compelling Value**: Intercepting secrets *inside the worktree prior to commit* prevents catastrophic leaks before they ever enter git commit DAGs, eliminating costly credential revocations, emergency key rotations, and git history scrubbing (`git-filter-repo`).

---
