---
id: '0043'
title: Non-Technical PMaC Onboarding Tutorial, Interactive Tour, and Discovery Sandbox
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0015
  - TASK-0039
  - TASK-0042
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0006
  - ADR-0007
  - ADR-0008
  - ADR-0009
governing_prds:
  - PRD-0003
governing_stories:
  - US-0050
target_bc: prd
---

# TASK-0043: Non-Technical PMaC Onboarding Tutorial, Interactive Tour, and Discovery Sandbox

## Summary
Author a dedicated Diataxis onboarding tutorial for product managers (`docs/tutorials/02-product-manager-onboarding.md`) and implement an interactive in-browser visualizer tour with a hands-on PRD discovery sandbox. Guide non-technical domain experts and PMs through PMaC principles, reading PRDs, writing executable Gherkin stories, and conducting UAT in business-friendly terms with zero terminal jargon. Embed a first-visit guided walkthrough in the web visualizer (tracked via `localStorage`) and an interactive in-browser exercise ("Create your first Idea PRD") that validates Markdown structure and awards a "PMaC Ready" badge.

## Problem Statement & Context
Project Management as Code (PMaC) offers enormous benefits in version locking and multi-agent coordination, but non-technical product managers, domain experts, and technical writers often feel alienated by terminal commands, raw git worktree concepts, and developer jargon. Without an approachable onboarding experience and guided interactive tour, PMs may resist PMaC adoption or revert to disconnected spreadsheets and wikis. SpecOps needs a welcoming, interactive pathway that makes PMs confident participants in git-backed workflows within 30 minutes.

## User Stories & Scenarios Satisfied
- **US-0050: Non-Technical PMaC Onboarding Tutorial and Interactive Guided Tour**
  - *Scenario: Accessing the Product Manager Diataxis Onboarding Tutorial*
  - *Scenario: Launching Interactive In-Browser Visualizer Guided Tour*
  - *Scenario: Completing the Guided First PRD Shaping Exercise*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Documentation tutorial `docs/tutorials/02-product-manager-onboarding.md` and visualizer tour module `src/spec_ops/visualizer/tour_script.py` remain strictly under 450 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that tutorial code snippets and sandbox markdown evaluation schemas validate deterministically against SpecOps core parser invariants without syntax errors or unhandled exceptions.
- **Mutmut Mutation Scope**: Interactive sandbox verification logic in `src/spec_ops/visualizer/tour_script.py` achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Building documentation via `spec-ops docs build` generates `site/tutorials/02-product-manager-onboarding.html`, providing step-by-step guidance on reading PRDs, authoring Gherkin, and conducting UAT without terminal jargon.
2. Opening the visualizer without prior tour completion flags in `localStorage` displays a welcome modal offering the 2-minute tour, highlighting PRDs & Features, Gantt timelines, UAT matrix, and deep links.
3. Completing the tour saves the completion state to `localStorage` and dismisses all tour overlays.
4. Completing the interactive "Create your first Idea PRD" sandbox exercise validates the Markdown structure locally and awards the "PMaC Ready: Your first specification is git-locked!" confirmation badge.
5. All scenarios verified via Playwright and blackbox `pytest-bdd` acceptance tests without private mock backdoors (ADR-0003, ADR-0006).
