---
id: 0009
title: Audit and Extract Runefoble System Patterns into SpecOps
status: Complete
created: 2026-09-29
completed: 2026-09-29
dependencies:
- TASK-0003
- TASK-0004
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0008
governing_prds:
- PRD-0001
governing_stories:
- US-0007
target_bc: core
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0009: Audit and Extract Runefoble System Patterns into SpecOps

## Summary
Audit the parent Runefoble repository to identify all reusable Project Management as Code patterns, agent constitutions (`AGENTS.md`), Diataxis documentation structures and sync mechanisms, preflight verification hooks, and developer CLI tooling that should be formally incorporated into SpecOps.

## Detailed Objectives
1. **Agent Constitution & Operational Rules (`AGENTS.md`)**:
   - Audited Runefoble's `AGENTS.md` for reusable structures: Hard Invariants, Product Navigation, Backlog Lifecycle rules, Diataxis Agent Instructions, Git Commit & Branching conventions, and Preflight checks.
   - Formalized in `docs/explanation/runefoble-system-patterns-audit.md` and `ADR-0008`.
2. **Diataxis Documentation Framework Integration**:
   - Evaluated Runefoble's four documentation quadrants (`tutorials/`, `how-to/`, `reference/`, `explanation/`).
   - Formalized in `ADR-0008` and created backlog tasks `TASK-0015` and `TASK-0021`.
3. **Developer Workflow & Preflight Tooling**:
   - Audited Makefile targets and `.pre-commit-config.yaml`.
   - Created candidate tasks `TASK-0018` (worktree rescue & takeover), `TASK-0019` (lockfile supply chain check), and `TASK-0020` (pre-commit hooks & proactive 400-line warnings).
4. **Slash Command & Agent Skill Adapters**:
   - Evaluated Antigravity skills and slash commands, mapped to `TASK-0014`.

## Completion Summary
- Created comprehensive extraction matrix in [`docs/explanation/runefoble-system-patterns-audit.md`](../../explanation/runefoble-system-patterns-audit.md).
- Authored and registered [`ADR-0008: Agent Constitution (AGENTS.md) and Diataxis Documentation Standards`](../../adrs/accepted/adr-0008-agent-constitution-and-diataxis-documentation-standards.md).
- Created backlog tasks `TASK-0018`, `TASK-0019`, `TASK-0020`, `TASK-0021` in `docs/project/backlog/proposed/` and registered in `PRIORITY.md`.
