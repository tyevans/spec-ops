---
id: '0002'
title: Architectural Profiles and Baseline ADR Registry
status: Complete
created: 2026-09-29
dependencies:
- TASK-0001
governing_adrs:
- ADR-0001
- ADR-0002
governing_prds:
- PRD-0001
governing_stories:
- US-0001
target_bc: profiles
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0002: Architectural Profiles and Baseline ADR Registry

## Summary
Implement profile registry supporting `core`, `bdd`, and `ddd` profiles, bundling 7 baseline ADRs, and providing collision-free dynamic renumbering.

## Definition of Done
1. Profile registry defines `core`, `bdd`, `ddd` with metadata and templates.
2. 7 baseline ADRs authored (Specification as Code, <500 lines limit, Blackbox verification, Preflight CI, Worktree isolation, BDD Gherkin, DDD Bounded Contexts).
3. Dynamic ADR resolution and renumbering verified by tests.
