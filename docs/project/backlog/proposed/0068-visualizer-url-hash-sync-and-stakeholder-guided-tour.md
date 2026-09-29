---
id: '0068'
title: Reactive URL Hash State Synchronization, Deep-Linked Permalinks, and Stakeholder Guided Tour
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0067
  - TASK-0022
governing_adrs:
  - ADR-0001
  - ADR-0003
  - ADR-0006
  - ADR-0007
governing_prds:
  - PRD-0005
governing_stories:
  - US-0103
  - US-0107
target_bc: visualizer
---

# TASK-0068: Reactive URL Hash State Synchronization, Deep-Linked Permalinks, and Stakeholder Guided Tour

## Summary
Implement client-side reactive URL hash state synchronization, shareable permalinks with automated canvas camera focal targeting, and an interactive non-technical stakeholder guided tour modal. Synchronize active view tabs, filter queries, and selected entity drawers into browser URL hashes (`#tab=matrix&filter=bc:core&entity=TASK-0056`), support seamless browser forward/back history navigation (`popstate`), smooth-pan the 2D canvas camera directly to deep-linked entity nodes, and provide an interactive onboarding walkthrough guiding non-technical stakeholders through BDD acceptance matrices and executable UAT sign-off verification.

## Problem Statement & Context
When team members share links to specific tasks or architectural decisions, recipient browsers often open to the default canvas view without context, forcing users to manually re-navigate tabs, type filters, and locate the node. Furthermore, non-technical product managers, designers, and business stakeholders struggle to navigate raw git specifications and complex graph networks. SpecOps requires URL hash state synchronization for effortless deep-linking and collaboration, paired with an interactive guided tour that surfaces executable BDD scenarios and formal UAT sign-off receipts.

## User Stories & Scenarios Satisfied
- **US-0103: Reactive URL Hash State Synchronization, Deep Linking, and Canvas Focus Permalinks**
  - *Scenario: Deep Linking to Specific View Tab and Entity Drawer on Load*
  - *Scenario: Bidirectional Synchronization of Filter State into URL Hash*
  - *Scenario: Browser Back and Forward History Traversal*
  - *Scenario: Graph Canvas Camera Focusing on Deep-Linked Node*
- **US-0107: Interactive Non-Technical Stakeholder Guided Tour and BDD Acceptance Matrix**
  - *Scenario: First-Time Stakeholder Interactive Onboarding Walkthrough*
  - *Scenario: Persona-Filtered BDD Acceptance Scenario Exploration*
  - *Scenario: Executable UAT Sign-Off Verification Matrix and Receipt Export*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: URL state router script generator in `src/spec_ops/visualizer/url_router_script.py` and guided tour script generator in `src/spec_ops/visualizer/tour_script.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across valid URL hash strings assert that parsing and re-serializing arbitrary state payloads (tabs, filters, entity selections) produces identical round-trip hash strings (hash state isomorphism).
- **Mutmut Mutation Scope**: URL hash parsing, state decoding, and filter serialization in `src/spec_ops/visualizer/url_router_script.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Opening the visualizer with `#tab=matrix&entity=TASK-0013` automatically activates the Matrix tab, opens the TASK-0013 detail drawer, and highlights linked stories.
2. Changing filter dropdowns or search queries updates the browser URL hash without triggering full page reloads.
3. Using browser Back and Forward navigation buttons restores previous filter states, drawer selections, and view tabs cleanly.
4. Opening the visualizer with `#tab=canvas&focus=TASK-0013` smoothly animates the 2D canvas camera to center on the target node at 1.5x zoom.
5. First-time users or clicking the "Guided Tour" button launches an interactive multi-step walkthrough explaining personas, PRD outcomes, and BDD scenario verification.
6. Non-technical users can filter BDD acceptance scenarios by persona and export a signed UAT verification markdown receipt.
7. All scenarios verified via public frontdoors and Playwright end-to-end browser automation without mock backdoors (ADR-0003, ADR-0006).
