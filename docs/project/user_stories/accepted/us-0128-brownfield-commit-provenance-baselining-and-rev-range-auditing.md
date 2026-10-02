---
id: '0128'
title: "Brownfield Commit Provenance Baselining and Rev-Range Auditing"
status: Accepted
created: 2026-10-02
persona: "Devon"
target_bc: "core"
feature: "FEAT-AUDIT-02"
governing_prd: "PRD-0007"
scenarios:
  - "Auditing commit provenance with adoption baseline commit"
  - "Verifying unbroken task trailers across specified revision ranges"
---

# US-0128 — Brownfield Commit Provenance Baselining and Rev-Range Auditing

## Governing PRD
- [`PRD-0007: Brownfield Codebase Adoption, Technical Debt Baselining & Documentation Bridging Engine`](../../product/accepted/prd-0007-brownfield-codebase-adoption-and-onboarding-engine.md)

## User Story

**As a** brownfield migration engineer (Devon),  
**I want** `spec-ops audit provenance` to support a baseline commit or `--since` revision parameter,  
**So that** pre-adoption legacy git commits (which predate SpecOps adoption) do not trigger false-positive unanchored provenance warnings or fail strict compliance audits.

## Acceptance Criteria

```gherkin
Scenario: Auditing commit provenance with adoption baseline commit
  Given an existing git repository adopted into SpecOps at commit "adoption_commit_hash"
  And "specops.toml" contains "[audit.provenance] baseline_commit = 'adoption_commit_hash'"
  When running "spec-ops audit provenance --strict"
  Then commits preceding the baseline commit are marked as grandfathered legacy history
  And only commits from the baseline forward are audited for "SpecOps-Task" RFC-822 trailers
  And the provenance integrity report outputs 100% compliant lineage.
```

```gherkin
Scenario: Verifying unbroken task trailers across specified revision ranges
  Given a brownfield repository with unanchored historical commits
  When running "spec-ops audit provenance --since main"
  Then the audit evaluates only commits in the specified range
  And ignores pre-existing unanchored history outside the range.
```
