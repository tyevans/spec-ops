---
id: '0016'
title: GitHub Pages Automated Publishing Workflow Template
status: Refined
created: 2026-09-29
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
---

# TASK-0016: GitHub Pages Automated Publishing Workflow Template

## Summary
Provide automated GitHub Actions workflow scaffolding (`.github/workflows/deploy-pages.yml`) to build the Diataxis documentation, compile the standalone interactive graph visualizer, and deploy the resulting static site to GitHub Pages on every push to `main`.

## Detailed Objectives
1. **GitHub Pages Workflow Template**:
   - Scaffold `.github/workflows/deploy-pages.yml` with least-privilege OIDC permissions (`pages: write`, `id-token: write`).
   - Run UV sync, documentation compiler, and visualizer bundle builder.
   - Upload and deploy `site/` directory with `actions/deploy-pages@v4`.
2. **Repository Configuration Support**:
   - Provide CLI option `spec-ops init --github-pages` or `spec-ops ci install --pages`.
3. **SpecOps Dogfooding**:
   - Enable GitHub Pages deployment in `spec-ops`'s own repository so documentation and the living 2D graph visualizer are publicly browsable at `https://tyevans.github.io/spec-ops/`.

## Definition of Done
1. `.github/workflows/deploy-pages.yml` template created and tested.
2. `spec-ops` repository configured with active GitHub Pages deployment workflow.
3. Successful workflow run uploads `site/` artifact and publishes live site.
