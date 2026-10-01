---
id: '0075'
title: Bidirectional End-to-End Traceability and Contributor Provenance Audit Engine
status: Complete
dependencies:
- TASK-0004
- TASK-0030
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0019
target_bc: core
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T11:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0075: Bidirectional End-to-End Traceability and Contributor Provenance Audit Engine

## Summary
Implement automated provenance and traceability auditing (`spec-ops audit provenance`) verifying unbroken commit trailers (`SpecOps-Task: TASK-XXXX`) from personas to commits, flagging unanchored changes, and attributing contributor provenance.

## Problem Statement & Context
As autonomous coding agents and human engineers commit changes concurrently, commits risk becoming disconnected from governing requirements. SpecOps requires an automated verification engine that scans git history, asserts every commit maps to an accepted task, story, and persona, and flags orphaned commits before integration.

## User Stories & Scenarios Satisfied
- **US-0019: Bidirectional End-to-End Traceability and Contributor Provenance Audit**
  - *Scenario: Verifying Unbroken Traceability from Persona to Merged Commits*
  - *Scenario: Flagging Unanchored Commits and Orphaned Tasks*
  - *Scenario: Contributor Provenance Attribution*

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Provenance auditor in `src/spec_ops/core/provenance.py` must stay strictly under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across arbitrary git commit logs assert that `spec-ops audit provenance` deterministically identifies commits missing `SpecOps-Task` trailers.
- **Mutmut Mutation Scope**: Commit trailer extraction and provenance graph pathfinding achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops audit provenance` validates unbroken commit trailers (`SpecOps-Task: TASK-XXXX`) from personas to commits.
2. Flagging any commit that lacks a corresponding task file in `docs/project/backlog/` with a non-zero exit code in `--strict` mode.
3. Attributing human vs autonomous agent contributions based on git trailers and signatures.
4. All scenarios verified via public frontdoor `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
