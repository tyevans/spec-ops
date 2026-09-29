---
id: '0066'
title: Interactive Guided Initialization Wizard and Headless CI Automation Scaffolding
status: Accepted
created: 2026-09-29
persona: Riley (The Human IC Developer)
feature: FEAT-SCAF-01
governing_prd: PRD-0005
---

# US-0066 — Interactive Guided Initialization Wizard and Headless CI Automation Scaffolding

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As a** software engineer setting up or onboarding a project to SpecOps,  
**I want** an interactive terminal initialization wizard that prompts for project topology, profiles, and workflow tooling, alongside headless flags for automated scripting,  
**So that** I can effortlessly bootstrap a compliant Project Management as Code environment with full visibility into generated artifacts without memorizing complex CLI syntax.

## Acceptance Criteria

```gherkin
Scenario: Interactive terminal onboarding wizard with live configuration preview
Given a clean terminal session in an uninitialized directory
When the developer runs "spec-ops init --interactive" in an interactive TTY
Then the wizard prompts for project name, architecture profiles (multi-select: core, bdd, ddd, security), CI provider (GitHub Actions, GitLab CI, or none), and documentation preferences
And displays a dry-run summary tree of files and baseline ADRs to be generated
And upon user confirmation, scaffolds the configured directory layout, "specops.toml", "AGENTS.md", and workflow files.
```
```gherkin
Scenario: Unattended headless initialization for CI and automation templates
Given a blank project directory in an automated script or CI runner
When the automation executes "spec-ops init --non-interactive --name MicroApp --profile core,bdd --ci github --diataxis --yes"
Then the command executes without prompting for stdin
And scaffolds the exact specified files with exit code 0
And writes a machine-readable initialization receipt to ".specops-scaffold.json" detailing created paths and profile checksums.
```
```gherkin
Scenario: Initialization dry-run preview mode
Given an existing codebase
When the developer runs "spec-ops init --profile core,bdd,ddd --dry-run"
Then no files or directories are written to disk
And the terminal outputs the planned file manifest, detected profile configurations, and any potential filename collisions.
```

## Rationale & Compelling Value
Bridges the gap between human onboarding and machine-driven automation, ensuring every repository starts with identical architectural hygiene regardless of how it was bootstrapped.

---
