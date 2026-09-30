---
id: '0069'
title: Reactive URL Hash State Synchronization, Deep-Linked Permalinks, and Canvas Focus
status: Refined
dependencies:
- TASK-0068
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
target_bc: visualizer
---

# TASK-0069: Reactive URL Hash State Synchronization, Deep-Linked Permalinks, and Canvas Focus

## Summary
Implement client-side reactive URL hash state synchronization, shareable permalinks with automated canvas camera focal targeting. Synchronize active view tabs, filter queries, and selected entity drawers into browser URL hashes (`#tab=matrix&filter=bc:core&entity=TASK-0058`), support seamless browser forward/back history navigation (`popstate`), and smooth-pan the 2D canvas camera directly to deep-linked entity nodes.

## Problem Statement & Context
When team members share links to specific tasks or architectural decisions, recipient browsers often open to the default canvas view without context, forcing users to manually re-navigate tabs, type filters, and locate the node. SpecOps requires URL hash state synchronization for effortless deep-linking and collaboration across all visualizer views.

## User Stories & Scenarios Satisfied
- **US-0103: Reactive URL Hash State Synchronization, Deep Linking, and Canvas Focus Permalinks**
  - *Scenario: Deep Linking to Specific View Tab and Entity Drawer on Load*
  - *Scenario: Bidirectional Synchronization of Filter State into URL Hash*
  - *Scenario: Browser Back and Forward History Traversal*
  - *Scenario: Graph Canvas Camera Focusing on Deep-Linked Node*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: URL state router script generator in `src/spec_ops/visualizer/url_router_script.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across valid URL hash strings assert that parsing and re-serializing arbitrary state payloads (tabs, filters, entity selections) produces identical round-trip hash strings (hash state isomorphism).
- **Mutmut Mutation Scope**: URL hash parsing, state decoding, and filter serialization in `src/spec_ops/visualizer/url_router_script.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Opening the visualizer with `#tab=matrix&entity=TASK-0013` automatically activates the Matrix tab, opens the TASK-0013 detail drawer, and highlights linked stories.
2. Changing filter dropdowns or search queries updates the browser URL hash without triggering full page reloads.
3. Using browser Back and Forward navigation buttons restores previous filter states, drawer selections, and view tabs cleanly.
4. Opening the visualizer with `#tab=canvas&focus=TASK-0013` smoothly animates the 2D canvas camera to center on the target node at 1.5x zoom.
5. All scenarios verified via public frontdoors and Playwright end-to-end browser automation without mock backdoors (ADR-0003, ADR-0006).
