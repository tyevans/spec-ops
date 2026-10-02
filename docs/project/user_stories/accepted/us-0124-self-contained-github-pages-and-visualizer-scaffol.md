---
id: '0124'
title: "Self-Contained GitHub Pages and Visualizer Scaffolding for Brownfield Repositories"
status: Accepted
created: 2026-10-02
persona: "Devon"
target_bc: "docs"
feature: "FEAT-ADOPT-02"
governing_prd: "PRD-0007"
scenarios:
  - "Scaffolding self-contained GitHub Pages deployment workflow without target lockfile dependency"
  - "Detecting pre-existing documentation tools and deployment workflows"
  - "Publishing interactive 2D graph visualizer alongside Diataxis documentation on GitHub Pages"
---

# US-0124 — Self-Contained GitHub Pages and Visualizer Scaffolding for Brownfield Repositories

## Governing PRD
- [`PRD-0007: Brownfield Codebase Adoption, Technical Debt Baselining & Documentation Bridging Engine`](../../product/accepted/prd-0007-brownfield-codebase-adoption-and-onboarding-engine.md)

## User Story

**As a** brownfield migration engineer (Devon),  
**I want** `spec-ops adopt` to scaffold a self-contained GitHub Pages deployment workflow that runs SpecOps via an isolated tool execution without contaminating the target project's `pyproject.toml`,  
**So that** existing projects (like redstring) automatically publish both their Diataxis documentation and the interactive living 2D graph visualizer to GitHub Pages without CI runtime failures or conflicts with pre-existing deploy workflows.

## Acceptance Criteria

```gherkin
Scenario: Scaffolding self-contained GitHub Pages deployment workflow without target lockfile dependency
  Given an existing brownfield project where SpecOps is not present in "pyproject.toml"
  When the migration engineer runs "spec-ops adopt --github-pages"
  Then ".github/workflows/deploy-pages.yml" is scaffolded
  And the workflow invokes "uv tool run --from git+https://... spec-ops docs build" (or published PyPI tool)
  And builds cleanly in clean GitHub Actions runner environments without requiring in-repo dependency modifications.
```

```gherkin
Scenario: Detecting pre-existing documentation tools and deployment workflows
  Given a target repository with an existing documentation configuration (such as "mkdocs.yml" or ".github/workflows/docs.yml")
  When "spec-ops adopt" or "spec-ops scaffold ci" inspects the repository
  Then it detects the duplicate or conflicting Pages deployment workflow
  And provides actionable guidance to bridge the living visualizer into the existing site or retire the legacy workflow.
```

```gherkin
Scenario: Publishing interactive 2D graph visualizer alongside Diataxis documentation on GitHub Pages
  Given the GitHub Pages site built by "spec-ops docs build"
  When deployed to GitHub Pages
  Then the documentation root serves the Diataxis documentation portal
  And the interactive 2D graph visualizer is available at "/visualizer/" with relationship graphs and burndown telemetry
  And every documentation page includes a header navigation link to "/visualizer/".
```

