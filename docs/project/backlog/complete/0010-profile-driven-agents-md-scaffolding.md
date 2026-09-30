---
id: '0010'
title: Profile-Driven AGENTS.md Constitution Scaffolding
status: Complete
created: 2026-09-29
completed: 2026-09-29
dependencies:
- TASK-0003
- TASK-0009
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0008
governing_prds:
- PRD-0001
governing_stories:
- US-0007
target_bc: scaffold
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0010: Profile-Driven AGENTS.md Constitution Scaffolding

## Summary
Enhance `spec-ops init` to scaffold an opinionated `AGENTS.md` file dynamically constructed from the selected architectural profiles (`core`, `bdd`, `ddd`), encoding hard invariants, backlog navigation, and preflight rules.

## Definition of Done
1. Scaffold engine generates `AGENTS.md` at project root with project name and profile rules.
2. Invariants list includes the installed baseline ADRs (file limit <500 lines, blackbox verification, worktree isolation).
3. Backlog workflow sections reference `docs/project/` and `spec-ops` CLI subcommands.
4. Blackbox tests verify `spec-ops init` generates a valid, conforming `AGENTS.md`.

## Completion Summary
- Created modular generator [`src/spec_ops/scaffold/agents_md.py`](../../../src/spec_ops/scaffold/agents_md.py) generating tailored constitutions based on selected profiles (`core`, `bdd`, `ddd`).
- Integrated into [`src/spec_ops/scaffold/init.py`](../../../src/spec_ops/scaffold/init.py).
- Added comprehensive blackbox tests in [`tests/test_scaffold.py`](../../../tests/test_scaffold.py) verifying profile-specific invariant inclusions.
- Compliant with ADR-0002 (<500 lines per file).
