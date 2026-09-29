---
id: '0009'
title: Audit and Extract Runefoble System Patterns into SpecOps
status: Refined
created: 2026-09-29
dependencies:
  - TASK-0003
  - TASK-0004
governing_adrs:
  - ADR-0001
  - ADR-0003
governing_prds:
  - PRD-0001
governing_stories:
  - US-0007
target_bc: core
---

# TASK-0009: Audit and Extract Runefoble System Patterns into SpecOps

## Summary
Audit the parent Runefoble repository to identify all reusable Project Management as Code patterns, agent constitutions (`AGENTS.md`), Diataxis documentation structures and sync mechanisms, preflight verification hooks, and developer CLI tooling that should be formally incorporated into SpecOps.

## Detailed Objectives
1. **Agent Constitution & Operational Rules (`AGENTS.md`)**:
   - Audit Runefoble's `AGENTS.md` for reusable structures: Hard Invariants, Product Navigation, Backlog Lifecycle rules, Diataxis Agent Instructions, Git Commit & Branching conventions, and Preflight checks.
   - Define a modular template engine in `spec_ops.scaffold` that generates custom `AGENTS.md` files based on selected profiles (`core`, `bdd`, `ddd`).
2. **Diataxis Documentation Framework Integration**:
   - Evaluate Runefoble's four documentation quadrants (`tutorials/`, `how-to/`, `reference/`, `explanation/`).
   - Determine whether SpecOps should scaffold Diataxis directory trees and provide a doc-sync verification command (`spec-ops docs audit/sync`).
3. **Developer Workflow & Preflight Tooling**:
   - Audit Makefile targets (`make preflight`, `make check`, `make test`).
   - Design git pre-commit / pre-push hook scaffolding to prevent committing files >500 lines or unsynchronized backlog tasks.
4. **Slash Command & Agent Skill Adapters**:
   - Evaluate Antigravity skills, slash commands (`/plan`, `/curate`, `/worker`, `/health`), and Cursor/Claude instructions.

## Definition of Done
1. Comprehensive audit matrix documenting candidate features, source files in Runefoble, and proposed SpecOps module destinations.
2. Concrete backlog tasks created and linked for each approved extraction candidate (`TASK-0010`, `TASK-0015+`).
3. Architectural Decision Record (or enhancement to ADR-0001) capturing the Agent Constitution and Diataxis standards.
