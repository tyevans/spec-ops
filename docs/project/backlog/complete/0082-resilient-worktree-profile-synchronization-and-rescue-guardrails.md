---
id: 0082
title: Resilient Worktree Profile Synchronization and Rescue Preflight Guardrails
status: Complete
dependencies:
- TASK-0024
- TASK-0051
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0010
- ADR-0011
- ADR-0012
governing_prds:
- PRD-0002
governing_stories:
- US-0051
- US-0108
target_bc: security
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0082: Resilient Worktree Profile Synchronization and Rescue Preflight Guardrails

## Summary
Ensure worktree lifecycle management (`spec-ops worker`, `spec-ops rescue`, and `spec-ops profile sync`) robustly synchronizes active architectural profile artifacts (`docs/project/SECURITY.md`, `specops.toml`, ADRs, and constitutional invariants) into isolated worktrees (`.worktrees/*`). Prevent false-positive preflight security policy violation failures during initial worktree creation and human takeover / rescue. Fix backlog isolation check in rescue manager to inspect `config.backlog_dir` rather than the parent `docs_dir`.

## Problem Statement & Context
When an enterprise repository enforces the security architectural profile, `spec-ops health --security` requires `docs/project/SECURITY.md` and `[security]` configuration. In multi-worktree execution environments, running `spec-ops profile sync security` from the main repository restores files in the repository root but leaves active worktrees in `.worktrees/` unsynchronized. Consequently, newly created or rescued worktrees fail initial preflight checks with "Security Policy Invariant Violated: docs/project/SECURITY.md is missing or invalid", halting autonomous workers and preventing human rescue. In addition, `WorktreeRescueManager`'s backlog isolation reset checked the parent `docs/project` path instead of `docs/project/backlog`, inadvertently reverting non-backlog documentation changes.

## User Stories & Scenarios Satisfied
- **US-0108: Enterprise Security Profile Scaffolding and Living Constitution Guardrails**
  - *Scenario: Synchronizing security profile across active worker worktrees and rescue preflight*
  - *Scenario: Preflight detection of degraded or missing security configuration*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Profile synchronization in `src/spec_ops/profiles/security.py`, rescue manager in `src/spec_ops/backlog/rescue.py`, worker engine in `src/spec_ops/backlog/worker.py`, and preflight in `src/spec_ops/worker/preflight.py` stay strictly below 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests verify that synchronizing profiles against any set of existing worktree directories deterministically creates compliant security files without corruption.
- **Mutmut Mutation Scope**: Worktree discovery and profile synchronization predicates achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops profile sync security` synchronizes both the root repository and all active task worktrees under `.worktrees/`.
2. Executing `spec-ops rescue <task-id> --complete` automatically synchronizes missing active profile artifacts before executing worktree preflight.
3. Executing `spec-ops worker` ensures isolated worktrees inherit active profile artifacts before running initial preflight checks.
4. Backlog isolation enforcement in `WorktreeRescueManager` isolates `docs/project/backlog` specifically, preserving other documentation files.
5. Acceptance verified via public frontdoor `pytest-bdd` tests and unit tests without mock backdoors (ADR-0003, ADR-0006).
