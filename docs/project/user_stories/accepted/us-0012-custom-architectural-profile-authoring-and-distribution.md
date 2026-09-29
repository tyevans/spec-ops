---
id: '0012'
title: Custom Architectural Profile Authoring and Multi-Repo Distribution
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-PRF-01
governing_prd: PRD-0005
---

# US-0012 — Custom Architectural Profile Authoring and Multi-Repo Distribution

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** agentic systems architect,  
**I want** to author, validate, and export custom architectural profile packages containing organization-specific ADRs, configuration presets, and agent constitution templates,  
**So that** all distributed microservices and autonomous agents across the engineering organization adhere to unified architectural standards and quality invariants.

## Acceptance Criteria

```gherkin
Scenario: Packaging a custom organizational profile
Given a local profile definition directory "profiles/fintech-service" containing custom ADRs and "profile.toml"
When the architect runs "spec-ops profiles package profiles/fintech-service --out dist/fintech-service.sop"
Then a verified profile bundle "dist/fintech-service.sop" is created
And the bundle contains validated ADR frontmatter, custom file limits, and agent rule fragments.
```

```gherkin
Scenario: Initializing a project using an exported custom profile bundle
Given a blank repository directory
And a custom profile bundle "fintech-service.sop"
When the architect runs "spec-ops init --profile dist/fintech-service.sop"
Then the custom organization ADRs are installed in "docs/project/adrs/accepted/"
And the generated "AGENTS.md" incorporates the custom profile's specific compliance invariants
And "specops.toml" records the installed profile identifier and version.
```

```gherkin
Scenario: Detecting conflicting or duplicate ADR numbers in composite profiles
Given an architect attempts to initialize a project with profiles "core" and an invalid custom profile reusing "ADR-0001"
When the architect runs "spec-ops init --profile core,./invalid-profile"
Then the command exits with code 1
And displays "Profile Error: Conflict detected for ADR-0001 between 'core' and 'invalid-profile'".
```

## Rationale & Compelling Value
Enables platform architects to distribute company-wide architectural decisions into versioned, composable bundles that bootstrap both human guidelines and AI agent constitutions without manual drift.
