---
id: '0106'
title: Milestone Scope Transition and Rollover Engine
status: Complete
dependencies:
- TASK-0067
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0077
target_bc: backlog
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T11:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0106: Milestone Scope Transition and Rollover Engine

## Summary
Implement automated milestone scope transitions (`spec-ops milestone rollover --from <M_SRC> --to <M_DST> [--dry-run]`) to roll over unfinished tasks from completed milestones to the next target milestone with atomic frontmatter updates.

## Problem Statement & Context
When a release milestone reaches its ship date or wraps up delivery, remaining low-priority or non-critical tasks must be transitioned cleanly into subsequent milestones. Manual editing of individual task markdown files across directories is error-prone and can introduce schema corruption. SpecOps requires an automated rollover command that atomically updates milestone metadata across unworked tasks.

## User Stories & Scenarios Satisfied
- **US-0077: Daily Curation Standup Digest, Stalled Claim Detection, and Milestone Scope Transition**
  - *Scenario: Transitioning Backlog Scope Across Milestone Boundaries*
    - Given a completed milestone with remaining unworked tasks
    - When the curator runs "spec-ops milestone rollover --from M1 --to M2"
    - Then unfinished tasks are reassigned to the next milestone and milestone tags in frontmatter are atomically updated.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Milestone rollover coordinator in `src/spec_ops/backlog/rollover.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across randomly generated task frontmatters assert that rollover only modifies target milestone fields while preserving all other frontmatter attributes verbatim.
- **Mutmut Mutation Scope**: Milestone filtering and frontmatter mutation logic in `src/spec_ops/backlog/rollover.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops milestone rollover --from M1 --to M2` reassigns unfinished tasks from M1 to M2.
2. Completed tasks in M1 remain untouched.
3. All acceptance criteria verified via public CLI frontdoors with `pytest-bdd` (ADR-0003, ADR-0006).
