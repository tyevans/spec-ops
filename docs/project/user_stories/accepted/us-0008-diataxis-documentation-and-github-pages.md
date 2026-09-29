---
id: '0008'
title: Diataxis Documentation System and GitHub Pages Publishing Pipeline
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-DOC-01
governing_prd: PRD-0001
---

# US-0008 — Diataxis Documentation System and GitHub Pages Publishing Pipeline

## Governing PRD
- [`PRD-0001: SpecOps Autonomous Project Management Engine`](../../product/accepted/prd-0001-spec-ops-autonomous-project-management-engine.md)

## User Story

**As an** engineering lead or system architect,  
**I want** `spec-ops` to scaffold a complete Diataxis documentation structure and a GitHub Pages deployment pipeline,  
**So that** all tutorials, how-to guides, reference specs, architectural explanations, and the living 2D graph visualizer are automatically published as a cohesive, searchable static site on every push to main.

## Acceptance Criteria

### Scenario 1: Scaffolding Diataxis Documentation Tree
```gherkin
Given a project initialized with SpecOps
When the developer runs "spec-ops init --diataxis"
Then "docs/" is populated with "tutorials/", "how-to/", "reference/", and "explanation/"
And starter index templates and Diataxis authoring directives are installed
And an operating manual synced from "AGENTS.md" is configured.
```

### Scenario 2: Compiling Static Site with Embedded Visualizer
```gherkin
Given documented Diataxis guides and project management specifications
When the builder runs "spec-ops docs build"
Then static HTML documentation is compiled to "site/"
And the standalone interactive visualizer is embedded at "site/visualizer/index.html"
And project graph metadata is exported to "site/project-data.json".
```

### Scenario 3: Automated Continuous Deployment to GitHub Pages
```gherkin
Given a GitHub repository configured with SpecOps
When changes are merged into the "main" branch
Then the ".github/workflows/deploy-pages.yml" GitHub Action triggers
And builds the Diataxis documentation site and visualizer
And deploys the artifact to GitHub Pages with ".nojekyll" and deep-linking enabled.
```
