---
id: '0125'
title: "Intelligent Pre-Existing Documentation Bridging and Workflow Deconfliction"
status: Accepted
created: 2026-10-02
persona: "Devon"
target_bc: "adopt"
feature: "FEAT-ADOPT-03"
governing_prd: "PRD-0007"
scenarios:
  - "Detecting pre-existing documentation tools and configuration files"
  - "Flagging and deconflicting duplicate GitHub Pages deployment workflows"
  - "Generating cross-navigation bridging guidance for legacy documentation sites"
---

# US-0125 — Intelligent Pre-Existing Documentation Bridging and Workflow Deconfliction

## Governing PRD
- [`PRD-0007: Brownfield Codebase Adoption, Technical Debt Baselining & Documentation Bridging Engine`](../../product/accepted/prd-0007-brownfield-codebase-adoption-and-onboarding-engine.md)

## User Story

**As a** brownfield migration engineer (Devon),  
**I want** `spec-ops adopt` to inspect the target repository for pre-existing documentation generators (e.g. MkDocs, Sphinx) and active GitHub Actions workflows,  
**So that** existing project teams do not encounter conflicting deployment jobs, clobbered GitHub Pages environments, or silent build overwrites during onboarding.

## Acceptance Criteria

```gherkin
Scenario: Detecting pre-existing documentation tools and configuration files
  Given an existing brownfield repository containing "mkdocs.yml" or "docs/conf.py"
  When the migration engineer runs "spec-ops adopt"
  Then the command detects the existing documentation framework
  And prints informational warnings outlining bridging and co-existence options.
```

```gherkin
Scenario: Flagging and deconflicting duplicate GitHub Pages deployment workflows
  Given a target repository with an existing workflow deploying to GitHub Pages under concurrency group "pages"
  When running "spec-ops adopt --github-pages"
  Then it detects the duplicate Pages deployment configuration
  And warns the user of the conflicting concurrency group
  And with "--deconflict-workflow" safely updates or namespaces the deployment workflow.
```

```gherkin
Scenario: Generating cross-navigation bridging guidance for legacy documentation sites
  Given a repository retaining an existing MkDocs documentation site
  When running "spec-ops adopt --bridge-docs"
  Then SpecOps outputs configuration recommendations to link the "/visualizer/" route from the existing navigation
  And provides artifact co-location directives without pipeline conflicts.
```
