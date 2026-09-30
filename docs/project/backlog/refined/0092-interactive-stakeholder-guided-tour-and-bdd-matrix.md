---
id: 0092
title: Interactive Stakeholder Guided Tour and Executable BDD Acceptance Matrix
status: Refined
dependencies:
- TASK-0069
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0006
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0107
target_bc: visualizer
---

# TASK-0092: Interactive Stakeholder Guided Tour and Executable BDD Acceptance Matrix

## Summary
Implement an interactive non-technical stakeholder guided tour and persona-filtered BDD acceptance scenario matrix within the living visualizer, with executable UAT sign-off receipt export.

## Problem Statement & Context
Non-technical product managers, executive leaders, and compliance auditors find raw git markdown specifications and complex relational graph visualizers daunting. SpecOps needs an interactive onboarding walkthrough and persona-filtered BDD scenario explorer in the visualizer that enables non-technical stakeholders to inspect test verification evidence and export verifiable UAT sign-off receipts.

## User Stories & Scenarios Satisfied
- **US-0107: Interactive Non-Technical Stakeholder Guided Tour and BDD Acceptance Matrix**
  - *Scenario: First-Time Stakeholder Interactive Onboarding Walkthrough*
  - *Scenario: Persona-Filtered BDD Acceptance Scenario Exploration*
  - *Scenario: Executable UAT Sign-Off Verification Matrix and Receipt Export*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Guided tour script generator in `src/spec_ops/visualizer/tour_script.py` and UAT receipt exporter must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that generated tour spotlight configs correctly reference existing visualizer DOM selectors and handle missing elements gracefully without JS runtime exceptions.
- **Mutmut Mutation Scope**: Tour step sequencing and persona filter state management in `src/spec_ops/visualizer/tour_script.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Opening the visualizer as a first-time user or clicking "Take Guided Tour" triggers an interactive spotlight overlay explaining PMaC, personas, and roadmap navigation.
2. Filtering by persona in "Personas & Stories" displays verified Gherkin scenarios with green test pass badges.
3. Clicking "Export UAT Verification Receipt" generates a tamper-evident compliance summary with Git commit SHAs, test run timestamps, and dual sign-off blocks.
4. All scenarios verified via public frontdoors and Playwright end-to-end browser automation without mock backdoors (ADR-0003, ADR-0006).
