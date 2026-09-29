---
id: '0013'
title: Interactive Terminal UI (TUI) Dashboard
status: Refined
dependencies:
- TASK-0004
- TASK-0005
governing_adrs:
- ADR-0001
governing_prds:
- PRD-0001
governing_stories:
- US-0006
target_bc: visualizer
---

# TASK-0013: Interactive Terminal UI (TUI) Dashboard

## Summary
Build an interactive terminal UI dashboard using Textual / Rich (`spec-ops tui`) to browse the entity graph, monitor backlog buffers, inspect file length metrics, and trigger manual curate or health operations.

## Definition of Done
1. `spec-ops tui` launches interactive terminal dashboard.
2. Views for Backlog Buffer, Entity Tree (Personas, PRDs, Stories, Tasks), and Health Invariants.
3. Keyboard shortcuts to trigger `curate`, `health`, and inspect task details.
