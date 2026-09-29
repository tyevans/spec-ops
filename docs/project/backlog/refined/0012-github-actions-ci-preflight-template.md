---
id: '0012'
title: GitHub Actions CI Quality Gate and Preflight Template
status: Refined
created: 2026-09-29
dependencies:
  - TASK-0005
governing_adrs:
  - ADR-0002
  - ADR-0004
governing_prds:
  - PRD-0001
governing_stories:
  - US-0002
target_bc: scaffold
---

# TASK-0012: GitHub Actions CI Quality Gate and Preflight Template

## Summary
Provide automated GitHub Actions workflow scaffolding (`.github/workflows/ci.yml`) enforcing `spec-ops health`, test suite execution, and file length invariant verification on pull requests and pushes.

## Definition of Done
1. Scaffold option to emit `.github/workflows/ci.yml`.
2. Workflow runs `uv run spec-ops health` and `uv run pytest`.
3. Workflow verifies that no PR introduces files >500 lines or breaks PRIORITY.md sync.
4. SpecOps' own repository configured with this workflow.
