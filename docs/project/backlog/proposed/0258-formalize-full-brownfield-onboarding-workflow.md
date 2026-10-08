---
id: '0258'
title: Formalize Full Brownfield Onboarding Workflow into spec-ops Skill
status: Proposed
dependencies: []
governing_prds:
- PRD-0001
governing_stories:
- US-0001
target_bc: orchestrator
---

## Summary
When onboarding brownfield projects (such as `redstring` and `eventsource-py`), the standard onboarding process should systematically execute:
1. Debt baseline generation (`.specops/grandfathered_debt.json`) and profile configuration.
2. Legacy ADR porting with SpecOps YAML frontmatter and retconning into `docs/project/adrs/`.
3. Archetypal Persona synthesis wave (`docs/project/user_stories/PERSONAS.md`).
4. BDD User Story wave per persona with executable Gherkin scenarios and blackbox verification status.
5. Living PRD authoring for uncovered core capabilities.
6. Documentation deconfliction and GitHub Pages deployment configuration for the interactive 2D living visualizer.

## Problem Statement
Standardize this complete brownfield onboarding workflow into the SpecOps orchestrator skill and CLI commands so future codebases can onboard with full living specifications out of the box.

## Acceptance Criteria
```gherkin
Given a brownfield repository with existing code and legacy ADRs
When spec-ops brownfield onboarding is executed
Then personas, BDD user stories, PRDs, and ADR registries are systematically generated and verified without manual intervention.
```
