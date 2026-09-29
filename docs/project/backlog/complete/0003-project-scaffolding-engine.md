---
id: '0003'
title: Project Scaffolding Engine and CLI Init
status: Complete
created: 2026-09-29
dependencies:
  - TASK-0001
  - TASK-0002
governing_adrs:
  - ADR-0001
  - ADR-0002
governing_prds:
  - PRD-0001
governing_stories:
  - US-0001
target_bc: scaffold
---

# TASK-0003: Project Scaffolding Engine and CLI Init

## Summary
Implement `spec-ops init` command to bootstrap repositories with the PMaC directory tree, baseline ADRs, default personas, `specops.toml`, and `.gitignore`.

## Definition of Done
1. `Scaffolder` recursively creates `docs/project/` (adrs, product, user_stories, backlog).
2. Generates initial personas (`Alex`, `Jordan`, `Morgan`) and README files.
3. Emits `specops.toml` with profile selection.
4. CLI tests verify idempotence and proper directory creation.
