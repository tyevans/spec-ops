---
id: '0123'
title: "Target Repository Virtualenv Dependency and License Resolution"
status: Accepted
created: 2026-10-02
persona: "Sasha"
target_bc: "security"
feature: "FEAT-SEC-05"
governing_prd: "PRD-0002"
scenarios:
  - "Inspecting target repository site-packages metadata"
  - "Resolving normalized licenses from target virtualenv"
  - "Gracefully falling back when virtualenv is not yet populated"
---

# US-0123 — Target Repository Virtualenv Dependency and License Resolution

## Governing PRD
- [`PRD-0002: Enterprise Security, Supply-Chain & Compliance Engine`](../../product/accepted/prd-0002-enterprise-security-supply-chain-and-compliance-engine.md)

## User Story

**As a** compliance officer and security architect (Sasha),  
**I want** `spec-ops audit dependencies` and `resolve_package_license` to inspect distribution metadata directly inside the target repository's `.venv/` site-packages,  
**So that** libraries and projects audited by SpecOps accurately discover installed package licenses and expressions rather than failing audits with false-positive UNKNOWN violations.

## Acceptance Criteria

```gherkin
Scenario: Inspecting target repository site-packages metadata
  Given a target repository with a local virtual environment located at ".venv/"
  When running "spec-ops audit dependencies" from the global or CLI installation
  Then distribution metadata is discovered using the target repository's site-packages search path
  And package license classifiers and License-Expression metadata from the target environment are extracted.
```

```gherkin
Scenario: Resolving normalized licenses from target virtualenv
  Given dependencies listed in "uv.lock" installed inside the target repository's ".venv"
  When resolving package licenses during preflight curation or security audits
  Then packages with valid OSI classifiers (e.g. MIT, BSD-3-Clause, Apache-2.0) are resolved to approved licenses
  And are not classified as "UNKNOWN".
```

```gherkin
Scenario: Gracefully falling back when virtualenv is not yet populated
  Given a target repository without a populated ".venv/" or in cold CI execution
  When running "spec-ops audit dependencies --offline"
  Then the resolver falls back to lockfile records, cache files, and known packages without crashing.
```

