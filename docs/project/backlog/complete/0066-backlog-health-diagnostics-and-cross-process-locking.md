---
id: '0066'
title: Proactive Backlog Health Diagnostics and Self-Healing Dependency Repair
status: Complete
dependencies:
- TASK-0065
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0005
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0075
target_bc: backlog
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T11:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0066: Proactive Backlog Health Diagnostics and Self-Healing Dependency Repair

## Summary
Implement proactive backlog health diagnostics and automated self-healing repair: deliver a dedicated backlog doctor tool (`spec-ops queue doctor [--fix]`) that detects broken dependency references, ghost index entries, unindexed task files, and broken links across `docs/project/backlog/`, providing automated in-place repair.

## Problem Statement & Context
As autonomous agents and human developers create, rename, and complete tasks across dozens of git worktrees, structural drift inevitably creeps into the backlog. Deleted task files leave dangling dependency pointers in remaining tasks, while manually created task files often fail to register in `PRIORITY.md`. SpecOps requires a self-healing backlog diagnostic doctor to automatically discover and resolve these discrepancies.

## User Stories & Scenarios Satisfied
- **US-0075: Proactive Backlog Health Diagnostics, Dangling Dependency Auditing, and Self-Healing Repair**
  - *Scenario: Detecting Broken and Dangling Dependency Pointers*
    - Given task documents referencing dependencies that do not exist on disk
    - When the architect runs `spec-ops queue doctor`
    - Then dangling dependency IDs are reported with file line numbers and exit code 1.
  - *Scenario: Detecting Ghost Entries and Unindexed Files in PRIORITY.md*
    - Given a task file present in `proposed/` but missing from `PRIORITY.md`
    - When `spec-ops queue doctor` audits the index
    - Then the discrepancy is flagged as an unindexed task error.
  - *Scenario: Automated Self-Healing Repair*
    - Given detected ghost entries and unindexed task files
    - When the architect runs `spec-ops queue doctor --fix`
    - Then `PRIORITY.md` is rebuilt atomically and dangling dependencies are cleaned up.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Backlog doctor implementation in `src/spec_ops/backlog/doctor.py` stays strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary corrupted backlog trees assert that `queue doctor --fix` idempotently restores a valid, zero-error state without data loss.
- **Mutmut Mutation Scope**: Dependency repair and index reconciliation logic in `src/spec_ops/backlog/doctor.py` achieves >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops queue doctor` audits all tasks and `PRIORITY.md`, reporting any dangling dependencies to non-existent tasks, unindexed task files on disk, or ghost entries in `PRIORITY.md`.
2. Executing `spec-ops queue doctor --fix` repairs missing `PRIORITY.md` references, cleans up ghost entries, and updates broken dependency pointers atomically.
3. All acceptance criteria verified via public frontdoor `pytest-bdd` tests without mock backdoors (ADR-0003, ADR-0006).
