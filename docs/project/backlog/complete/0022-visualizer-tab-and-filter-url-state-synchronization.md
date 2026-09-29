---
id: '0022'
title: Visualizer Tab and Filter URL State Synchronization
status: Complete
dependencies:
- TASK-0017
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0006
governing_prds:
- PRD-0001
governing_stories:
- US-0010
target_bc: visualizer
---

# TASK-0022: Visualizer Tab and Filter URL State Synchronization

## Summary
Implement client-side URL hash routing and bidirectional state synchronization for the SpecOps multi-view visualizer, allowing users to bookmark, share, and navigate across dashboard tabs (`graph`, `gantt`, `kanban`, `prds`, `adrs`, `personas`) and faceted filters (`q`, `status`, `bc`, `hideDone`, `groupBy`) with browser back/forward history support.

## Problem Statement
Currently, the SpecOps visualizer maintains all navigation and filter state ephemerally in JavaScript runtime variables (`activeTab`, `filterState`). Reloading the page resets the view to the default 2D graph, browser back/forward navigation is non-functional, and users cannot share direct links to a filtered Kanban column, Gantt timeline horizon, or ADR radar view.

## Detailed Objectives
1. **Hash Routing & URL Parser**:
   - Implement a lightweight, zero-dependency URL hash parser and serializer (e.g., `#tab=kanban&status=refined&q=rescue&hideDone=true`).
   - Read and parse initial state from `window.location.hash` upon page initialization.
2. **Bidirectional State Sync**:
   - Update the URL hash via `history.replaceState` or `history.pushState` whenever tabs are switched or filters change.
   - Listen to `window.addEventListener('hashchange')` and `popstate` to restore UI tab and filter controls when browser history navigation occurs.
3. **Multi-View Compatibility**:
   - Ensure all 6 dashboard views (`graph`, `gantt`, `kanban`, `prds`, `adrs`, `personas`) restore and render correctly when loaded directly from a deep-linked URL.
   - Synchronize text inputs and dropdown selects with URL parameters on mount.
4. **Standalone Bundle Invariant**:
   - Retain zero external JavaScript/CSS library dependencies. Works identically in `spec-ops visualizer --serve` and offline single-file bundles opened via `file://`.
   - Maintain strict file length limits (<500 lines per file).

## Definition of Done (Blackbox Frontdoor TDD)
1. Visualizer HTML bundle parses URL hash parameters on load and activates requested tab and filter states.
2. Changing tabs or filters updates the browser URL hash without full page reloads.
3. Browser Back/Forward buttons navigate between visited visualizer tabs and filter configurations.
4. Python generator tests verify template generation with hash routing scripts.
5. `spec-ops health` reports 0 file limit violations and 0 warnings.
