---
id: '0016'
title: GitHub Pages Automated Publishing Workflow Template
status: Complete
created: 2026-09-29
completed: 2026-09-29
dependencies:
- TASK-0012
- TASK-0015
governing_adrs:
- ADR-0001
- ADR-0004
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


# TASK-0016: GitHub Pages Automated Publishing Workflow Template

## Summary
Provide automated GitHub Actions workflow scaffolding (`.github/workflows/deploy-pages.yml`) to build the Diataxis documentation, compile the standalone interactive graph visualizer, and deploy the resulting static site to GitHub Pages on every push to `main`.

## Definition of Done
1. `.github/workflows/deploy-pages.yml` template created and tested.
2. `spec-ops` repository configured with active GitHub Pages deployment workflow.
3. Successful workflow run uploads `site/` artifact and publishes live site.

## Completion Summary
- Created [`src/spec_ops/scaffold/pages_workflow.py`](../../../src/spec_ops/scaffold/pages_workflow.py) providing `generate_pages_workflow` with least-privilege OIDC permissions (`pages: write`, `id-token: write`, `contents: read`), UV environment setup, Diataxis docs compilation via `uv run spec-ops docs build`, artifact packaging with `actions/upload-pages-artifact@v3`, and deployment via `actions/deploy-pages@v4`.
- Integrated `--github-pages` and `--no-github-pages` flags into `spec-ops init` and [`init_project`](../../../src/spec_ops/scaffold/init.py).
- Configured `.github/workflows/deploy-pages.yml` directly in the `spec-ops` repository.
- Added comprehensive unit and blackbox tests in [`tests/test_scaffold.py`](../../../tests/test_scaffold.py).
- All source files strictly comply with Hard Invariant 1 (<500 lines).
