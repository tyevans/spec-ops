---
id: '0069'
title: Multi-Platform CI/CD Pipeline Scaffolding Across GitHub Actions and GitLab CI
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-SCAF-04
governing_prd: PRD-0005
---

# US-0069 — Multi-Platform CI/CD Pipeline Scaffolding Across GitHub Actions and GitLab CI

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** AI-native engineering lead,  
**I want** `spec-ops` to scaffold standardized, platform-native CI quality gate pipelines for GitHub Actions and GitLab CI,  
**So that** our hybrid human-agent engineering teams enjoy identical, enforceable preflight verification, lockfile checks, and SpecOps invariant enforcement regardless of which enterprise git hosting platform we use.

## Acceptance Criteria

```gherkin
Scenario: Scaffolding a GitLab CI quality pipeline
Given a project initialized with SpecOps
When the engineer runs "spec-ops scaffold ci --platform gitlab"
Then a ".gitlab-ci.yml" file is generated at the repository root
And the pipeline includes stages for dependency lockfile validation ("uv lock --check"), invariant health scanning ("uv run spec-ops health"), and blackbox test execution ("uv run pytest")
And configures persistent caching for UV dependencies.
```
```gherkin
Scenario: Scaffolding multi-platform CI pipelines simultaneously
Given an organization maintaining mirrored repositories across GitHub and GitLab
When the engineer runs "spec-ops scaffold ci --platform all"
Then both ".github/workflows/ci.yml" and ".gitlab-ci.yml" are created
And both configurations execute the exact same sequence of quality checks and invariant gates.
```
```gherkin
Scenario: Updating existing CI workflow on toolchain version bump
Given an existing ".github/workflows/ci.yml" generated with Python 3.12
When the engineer updates "specops.toml" to target Python 3.13 and runs "spec-ops scaffold ci --update"
Then the CI workflow file is updated to Python 3.13 without removing custom organizational job steps marked with preservation tags.
```

## Rationale & Compelling Value
Guarantees parity between local developer environments and remote CI across multiple hosting platforms, preventing "works on my machine but fails on GitLab" discrepancies.

---
