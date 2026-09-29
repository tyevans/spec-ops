---
id: '0067'
title: Hierarchical Profile Inheritance, Composition, and Invariant Overrides
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-SCAF-02
governing_prd: PRD-0005
---

# US-0067 — Hierarchical Profile Inheritance, Composition, and Invariant Overrides

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** agentic systems architect,  
**I want** to define composite architectural profiles that inherit from parent profiles and override specific invariant thresholds, vertical slice definitions, and quality gates,  
**So that** platform teams can standardize enterprise-wide architectural foundations while tailoring specific domain constraints across microservices and bounded contexts.

## Acceptance Criteria

```gherkin
Scenario: Defining a custom profile inheriting from parent profiles
Given a profile definition file "profiles/enterprise-fintech/profile.toml"
And the profile specifies "extends = ['core', 'security', 'ddd']"
And defines custom vertical slices for audit trails and regulatory compliance
When the architect runs "spec-ops profiles validate profiles/enterprise-fintech"
Then the profile dependency tree resolves without circular dependencies
And aggregates all inherited baseline ADRs sequentially without slug collisions.
```
```gherkin
Scenario: Overriding specific invariant thresholds in a derived profile
Given an inherited profile "enterprise-fintech" extending "core"
And "profile.toml" configures "[overrides.architecture] file_length_limit = 350" and "[overrides.quality] require_mutation_testing = true"
When a project is initialized with "spec-ops init --profile ./profiles/enterprise-fintech"
Then "specops.toml" is generated with "file_length_limit = 350"
And "AGENTS.md" reflects the strict 350-line limit in its Hard Invariants section
And the generated ADR registry incorporates both base and enterprise-specific ADRs.
```
```gherkin
Scenario: Detecting circular inheritance and conflicting invariant overrides
Given profile "profile-a" extending "profile-b" and "profile-b" extending "profile-a"
When the architect runs "spec-ops profiles validate profiles/profile-a"
Then the validation fails with exit code 1
And displays "Profile Inheritance Error: Circular dependency detected (profile-a -> profile-b -> profile-a)".
```

## Rationale & Compelling Value
Solves the enterprise governance dilemma—central platform teams retain control over mandatory baseline invariants while product teams retain the autonomy to enforce tighter rules or domain slices.

---
