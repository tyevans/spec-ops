---
id: 0068
title: Portable Standalone Visualizer Bundle Export and Unified Multi-Perspective
  Project Matrix
status: Complete
dependencies:
- TASK-0008
- TASK-0017
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0006
- ADR-0007
governing_prds:
- PRD-0005
governing_stories:
- US-0101
- US-0102
- US-0026
target_bc: visualizer
---

# TASK-0068: Portable Standalone Visualizer Bundle Export and Unified Multi-Perspective Project Matrix

## Summary
Deliver an air-gapped, zero-dependency standalone HTML visualizer bundle export (`spec-ops visualizer export --output dist/index.html`) and a unified multi-perspective project matrix interface. In-line all CSS, SVG icons, and vanilla JavaScript into a single self-contained artifact runnable over local `file://` protocols in air-gapped environments. Implement a unified multi-tab dashboard shell featuring 2D force-directed canvas, Gantt delivery timelines, multi-dimensional relational matrix tables with instant cross-filtering (by status, persona, milestone, and bounded context), and an engineering lead console with live agent fleet telemetry.

## Problem Statement & Context
Stakeholders, clients, and developers in air-gapped or restricted security networks cannot rely on hosted web servers, CDN scripts, or background databases to inspect project architecture. Furthermore, viewing project specifications across isolated files makes it difficult to see how PRDs, ADRs, user stories, and backlog tasks interlock. SpecOps requires a single-file portable visualizer bundle that embeds all graph data, supports rich relational cross-filtering, and renders instantaneous matrix perspectives completely offline.

## User Stories & Scenarios Satisfied
- **US-0101: Zero-Dependency Portable Visualizer Bundle and Air-Gapped Export**
  - *Scenario: Compiling Single-File Standalone HTML Bundle*
  - *Scenario: Air-Gapped Offline Execution via Local File Protocol*
  - *Scenario: Automated Documentation Site Asset Generation*
- **US-0102: Unified Multi-Perspective Project Matrix with Relational Cross-Filtering**
  - *Scenario: Seamless Multi-Tab Dashboard Navigation Shell*
  - *Scenario: Cross-Entity Relational Pivoting from PRDs and ADRs to Backlog Tasks*
  - *Scenario: Delivery Horizon and Bounded Context Grouping in Gantt Timeline*
  - *Scenario: Real-Time Faceted Search and Bounded Context Isolation*
- **US-0026: Living Visualizer Lead Console with Real-Time Agent Fleet Telemetry**
  - *Scenario: Live Agent Fleet and Worktree Telemetry*
  - *Scenario: Real-Time Alerts for Stalled Tasks Requiring Human Rescue*
  - *Scenario: One-Click Rescue Launch*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Visualizer bundle compiler in `src/spec_ops/visualizer/bundle.py`, matrix view generator in `src/spec_ops/visualizer/matrix.py`, and lead console script generator in `src/spec_ops/visualizer/lead_console.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` assert that the generated standalone HTML bundle contains zero external URL references (`http://` or `https://` script/style tags), ensuring 100% offline air-gapped compatibility.
- **Mutmut Mutation Scope**: Data inlining and HTML serialization in `src/spec_ops/visualizer/bundle.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops visualizer export --output dist/index.html` generates a self-contained HTML file under 2MB containing all embedded graph nodes, edges, and application logic.
2. Opening `dist/index.html` directly via `file://` in a modern browser with network disabled renders all views cleanly with zero console script or resource loading errors.
3. Switching between Canvas, Matrix, Timeline, and Lead Console tabs occurs seamlessly in under 50ms without full page reloads.
4. Clicking an entity in the Matrix table pivots to its linked PRD, story, or ADR detail drawer showing downstream tasks and implementation status.
5. Lead Console view displays live active worktree allocations, stalled task alerts, and one-click CLI rescue commands.
6. All scenarios verified via public frontdoor tests and Playwright headless browser automation without mock backdoors (ADR-0003, ADR-0006).
