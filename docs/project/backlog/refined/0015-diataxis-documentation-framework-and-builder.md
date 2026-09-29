---
id: '0015'
title: Diataxis Documentation Framework Scaffolding and Static Site Builder
status: Refined
created: 2026-09-29
dependencies:
  - TASK-0003
  - TASK-0008
  - TASK-0010
governing_adrs:
  - ADR-0001
  - ADR-0002
governing_prds:
  - PRD-0001
governing_stories:
  - US-0008
target_bc: scaffold
---

# TASK-0015: Diataxis Documentation Framework Scaffolding and Static Site Builder

## Summary
Incorporate the 4-quadrant Diataxis documentation system (`tutorials/`, `how-to/`, `reference/`, `explanation/`) into `spec-ops scaffold` and provide a built-in documentation compiler (`spec-ops docs build`) that synchronizes `AGENTS.md` -> `operating-manual.md`, embeds the 2D visualizer into `site/visualizer/`, and exports `project-data.json`.

## Detailed Objectives
1. **Diataxis Scaffolding (`spec-ops init --diataxis`)**:
   - Create directories: `docs/tutorials/`, `docs/how-to/`, `docs/reference/`, `docs/explanation/`.
   - Scaffold starter files: `index.md`, `operating-manual.md` (synchronized from `AGENTS.md`), and Diataxis contributor guidelines.
2. **Static Site Build Engine (`spec-ops docs build`)**:
   - Provide a clean documentation builder (using MkDocs Material, Zensical, or lightweight Markdown-to-HTML parser).
   - Automatically compile `dist/visualizer.html` and embed it at `site/visualizer/index.html`.
   - Export full project graph to `site/project-data.json`.
   - Generate `.nojekyll` and search indices.
3. **Diataxis Agent Directives**:
   - Embed Diataxis maintenance rules directly into the generated `AGENTS.md`:
     - *Inform work with existing docs*
     - *Fix inaccurate or stale docs*
     - *Produce guides for generic / reusable patterns*

## Definition of Done
1. `spec-ops init --diataxis` scaffolds the complete 4-quadrant documentation tree.
2. `spec-ops docs build` generates a standalone `site/` folder with documentation HTML, search index, embedded visualizer, and `project-data.json`.
3. Unit and CLI integration tests verify zero regressions.
