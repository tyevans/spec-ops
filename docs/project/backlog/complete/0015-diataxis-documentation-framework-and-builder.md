---
id: '0015'
title: Diataxis Documentation Framework Scaffolding and Static Site Builder
status: Complete
created: 2026-09-29
completed: 2026-09-29
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
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0015: Diataxis Documentation Framework Scaffolding and Static Site Builder

## Summary
Incorporate the 4-quadrant Diataxis documentation system (`tutorials/`, `how-to/`, `reference/`, `explanation/`) into `spec-ops scaffold` and provide a built-in documentation compiler (`spec-ops docs build`) that synchronizes `AGENTS.md` -> `operating-manual.md`, embeds the 2D visualizer into `site/visualizer/`, and exports `project-data.json`.

## Definition of Done
1. `spec-ops init --diataxis` scaffolds the complete 4-quadrant documentation tree.
2. `spec-ops docs build` generates a standalone `site/` folder with documentation HTML, search index, embedded visualizer, and `project-data.json`.
3. Unit and CLI integration tests verify zero regressions.

## Completion Summary
- Created [`src/spec_ops/scaffold/diataxis.py`](../../../src/spec_ops/scaffold/diataxis.py) providing `scaffold_diataxis_docs` to scaffold `docs/tutorials/`, `docs/how-to/`, `docs/reference/`, `docs/explanation/`, `index.md`, `contributing.md`, and `operating-manual.md`.
- Wired `--diataxis` and `--no-diataxis` CLI options into `spec-ops init` and [`init_project`](../../../src/spec_ops/scaffold/init.py).
- Created [`src/spec_ops/docs/builder.py`](../../../src/spec_ops/docs/builder.py) and [`src/spec_ops/docs/templates.py`](../../../src/spec_ops/docs/templates.py) to compile Markdown documentation to semantic HTML with responsive Diataxis sidebar navigation, dynamic doc discovery, `.md` link rewriting, search index generation (`search-index.json`), `.nojekyll`, project data serialization (`project-data.json`), and embedded 2D visualizer bundle (`site/visualizer/index.html`).
- Added CLI subcommands `spec-ops docs build` and wired doc site compilation directly into `spec-ops cycle`.
- Updated [`scripts/build_docs.py`](../../../scripts/build_docs.py) to delegate to `build_docs_site`.
- Added comprehensive unit and CLI blackbox tests in [`tests/test_docs.py`](../../../tests/test_docs.py).
- All source files strictly comply with Hard Invariant 1 (<500 lines).
