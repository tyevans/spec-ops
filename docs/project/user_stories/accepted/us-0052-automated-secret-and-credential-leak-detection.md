---
id: '0052'
title: Automated Secret and Credential Leak Detection in Agent Worktrees
status: Accepted
created: 2026-09-29
persona: Sasha (The Trust & Security Officer)
feature: FEAT-SEC-02
governing_prd: PRD-0002
---

# US-0052 — Automated Secret and Credential Leak Detection in Agent Worktrees

## Governing PRD
- [`PRD-0002: Enterprise Security, Supply-Chain & Compliance Engine`](../../product/accepted/prd-0002-enterprise-security-supply-chain-and-compliance-engine.md)

## User Story

**As an** trust and security officer,  
**I want** `spec-ops health --security` and autonomous worker preflight verification to scan staged and unstaged worktree diffs for exposed credentials and high-entropy secrets,  
**So that** autonomous agents cannot commit API keys, cloud access tokens, or private credentials into version control history.

## Acceptance Criteria

```gherkin
Scenario: Blocking commits containing high-entropy secrets or private tokens
Given an autonomous agent worktree where the agent has written an OpenAI API key or AWS secret access key into a source file
When the worker engine executes preflight verification prior to git commit
Then "spec-ops health --security" detects the high-entropy credential pattern
And the preflight check exits with returncode 1, aborting the commit
And diagnostic feedback listing the offending file path and masked token snippet is returned to the agent prompt for self-healing remediation.
```

```gherkin
Scenario: Clean worktree passes preflight credential scan
Given an autonomous agent worktree with valid feature modifications containing zero credentials, private keys, or tracked .env files
When the preflight command "spec-ops health --security" executes
Then the check exits with returncode 0
And reports "Security Invariant Met: 0 credential leaks detected".
```

## Rationale & Compelling Value
In-worktree credential detection stops leaks before git commits are ever created or pushed upstream, eliminating emergency key rotation incidents.
