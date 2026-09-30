---
id: 0083
title: Multi-Platform CI/CD Pipeline Scaffolding Across GitHub Actions and GitLab
  CI
status: Complete
dependencies:
- TASK-0064
- TASK-0012
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0004
- ADR-0007
- ADR-0008
governing_prds:
- PRD-0005
governing_stories:
- US-0069
target_bc: scaffold
---

# TASK-0083: Multi-Platform CI/CD Pipeline Scaffolding Across GitHub Actions and GitLab CI

## Summary
Implement multi-platform continuous integration workflow scaffolding (`spec-ops scaffold ci --platform <github|gitlab|all>`) that generates preflight verification workflows for GitHub Actions (`.github/workflows/specops.yml`) and GitLab CI (`.gitlab-ci.yml`). Ensure generated pipelines execute `uv run spec-ops health`, verify zero-dependency supply-chain lockfiles, run blackbox frontdoor test suites, and support matrix testing across supported Python runtimes.

## Problem Statement & Context
Engineering organizations use different CI/CD platforms (e.g. GitHub Actions, GitLab CI). Writing and maintaining bespoke workflow YAML configurations across repositories often results in skipped health checks, missing lockfile verification steps, or outdated Python environment setup. SpecOps requires automated multi-platform CI pipeline generators to guarantee that every repository enforces identical PMaC quality and security gates regardless of hosting platform.

## User Stories & Scenarios Satisfied
- **US-0069: Multi-Platform CI/CD Pipeline Scaffolding Across GitHub Actions and GitLab CI**
  - *Scenario: Scaffolding a GitLab CI quality pipeline*
    - Given a repository configured with SpecOps
    - When the architect runs "spec-ops scaffold ci --platform gitlab"
    - Then ".gitlab-ci.yml" is generated containing stages for lint, health, test, and security.
  - *Scenario: Scaffolding multi-platform CI pipelines simultaneously*
    - Given a project needing both GitHub and GitLab pipeline configurations
    - When "spec-ops scaffold ci --platform all" is executed
    - Then both ".github/workflows/specops.yml" and ".gitlab-ci.yml" are written with matrix definitions.
  - *Scenario: Updating existing CI workflow on toolchain version bump*
    - Given an existing ".github/workflows/specops.yml"
    - When the developer runs "spec-ops scaffold ci --platform github --force"
    - Then workflow steps are updated with latest toolchain actions while preserving custom environment variables.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: CI pipeline scaffolding module in `src/spec_ops/scaffold/ci_multi.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary matrix configurations and platform targets assert that all generated YAML manifests parse as valid, strictly-typed schemas without syntax errors.
- **Mutmut Mutation Scope**: Workflow template interpolation and matrix variable expansion in `src/spec_ops/scaffold/ci_multi.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops scaffold ci --platform github` generates `.github/workflows/specops.yml` with health, test, and lockfile steps.
2. Executing `spec-ops scaffold ci --platform gitlab` generates `.gitlab-ci.yml` with stages and cache directives.
3. Executing `spec-ops scaffold ci --platform all` generates both pipeline manifests cleanly.
4. Attempting to overwrite existing CI files without `--force` prompts for confirmation or aborts with code 1.
5. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
