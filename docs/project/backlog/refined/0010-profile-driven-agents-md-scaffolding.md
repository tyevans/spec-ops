---
id: '0010'
title: Profile-Driven AGENTS.md Constitution Scaffolding
status: Refined
created: 2026-09-29
dependencies:
  - TASK-0003
  - TASK-0009
governing_adrs:
  - ADR-0001
  - ADR-0002
governing_prds:
  - PRD-0001
governing_stories:
  - US-0007
target_bc: scaffold
---

# TASK-0010: Profile-Driven AGENTS.md Constitution Scaffolding

## Summary
Enhance `spec-ops init` to scaffold an opinionated `AGENTS.md` file dynamically constructed from the selected architectural profiles (`core`, `bdd`, `ddd`), encoding hard invariants, backlog navigation, and preflight rules.

## Definition of Done
1. Scaffold engine generates `AGENTS.md` at project root with project name and profile rules.
2. Invariants list includes the installed baseline ADRs (file limit <500 lines, blackbox verification, worktree isolation).
3. Backlog workflow sections reference `docs/project/` and `spec-ops` CLI subcommands.
4. Blackbox tests verify `spec-ops init` generates a valid, conforming `AGENTS.md`.
