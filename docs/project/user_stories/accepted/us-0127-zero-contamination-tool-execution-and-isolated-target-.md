---
id: '0127'
title: "Zero-Contamination Tool Execution and Isolated Target Environment Inspection"
status: Accepted
created: 2026-10-02
persona: "Devon"
target_bc: "core"
feature: "FEAT-ADOPT-04"
governing_prd: "PRD-0007"
scenarios:
  - "Running SpecOps commands on external target directory without lockfile modification"
  - "Inspecting target virtual environment site-packages for accurate license and import auditing"
  - "Falling back safely when target virtualenv is unpopulated or in isolated CI"
---

# US-0127 — Zero-Contamination Tool Execution and Isolated Target Environment Inspection

## Governing PRD
- [`PRD-0007: Brownfield Codebase Adoption, Technical Debt Baselining & Documentation Bridging Engine`](../../product/accepted/prd-0007-brownfield-codebase-adoption-and-onboarding-engine.md)

## User Story

**As a** brownfield migration engineer (Devon),  
**I want** to execute SpecOps verification, audit, and documentation compilation commands against an external target directory without requiring `spec-ops` to be declared in the target repo's dependencies,  
**So that** external production repositories maintain pure lockfiles and clean supply chains while benefiting from SpecOps governance.

## Acceptance Criteria

```gherkin
Scenario: Running SpecOps commands on external target directory without lockfile modification
  Given an external repository directory without SpecOps listed in "pyproject.toml"
  When executing "spec-ops health --dir <path>" or "spec-ops docs build --dir <path>"
  Then the target repository's "pyproject.toml" and "uv.lock" remain strictly untouched
  And all operations execute cleanly in memory or target artifact paths.
```

```gherkin
Scenario: Inspecting target virtual environment site-packages for accurate license and import auditing
  Given an external repository with its own ".venv/" virtual environment
  When running SpecOps dependency and architecture audits against the target directory
  Then installed packages, metadata, and license expressions are discovered from the target environment
  And do not bleed into or conflict with the host SpecOps runtime environment.
```

```gherkin
Scenario: Falling back safely when target virtualenv is unpopulated or in isolated CI
  Given a target repository checked out cleanly in CI without a populated local virtualenv
  When running audit or build commands with "--offline" or in standalone mode
  Then the tool inspects lockfiles, manifest files, and static schemas without throwing unhandled exceptions.
```
