---
id: '0253'
title: Architectural Decision Record Amendment Workflow Engine, CLI, Cycle Detection, and DoR Validation
status: Complete
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0006
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0130
target_bc: core
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-04T20:30:00+00:00'
commit_signature_status: SIGNED
persona: Alex
has_signed_commits: true
mutation_scope:
- src/spec_ops/adrs
---

# TASK-0253: Architectural Decision Record Amendment Workflow Engine, CLI, Cycle Detection, and DoR Validation

## Summary
Implement first-class non-destructive Architectural Decision Record (ADR) amendment lifecycle capabilities alongside supersession:
1. Provide core amendment engine `ADRAmendmentEngine` supporting `spec-ops adr amend <old-id> [--title <title> | --by <new-id>]`.
2. Maintain bidirectional frontmatter lineage metadata (`amends:` in amending ADR, `amended_by:` in target ADR) while keeping the target ADR status as active (`Accepted`).
3. Synchronize `docs/project/adrs/REGISTRY.md` to reflect the amendment without marking the predecessor as `Superseded`.
4. Implement cycle detection raising `CircularAmendmentError` on circular amendment graphs before disk modification.
5. Preserve active status and task validity in Definition of Ready (DoR) gates and prevent `spec-ops reconciler` from replacing amended ADRs.

## Problem Statement & Context
SpecOps previously only supported binary supersession, which completely retired predecessor ADRs (`status: Superseded`). In real-world software architecture (such as Redstring with 16+ amendment chains), architectural decisions evolve incrementally (e.g. ADR-0136 amends ADR-0101's version table, but ADR-0101's foundational event log granularity stands). Retiring ADR-0101 breaks task governance under DoR gates and falsifies knowledge graph state. First-class amendments enable non-destructive evolution.

## Detailed Objectives
1. **Core Domain & Engine**:
   - Create `src/spec_ops/adrs/amend.py` and `src/spec_ops/adrs/amendment.py`.
   - Implement `CircularAmendmentError`, `AmendResult`, `detect_amendment_cycles`, `discover_amended_adrs`, and `update_registry_amendment`.
   - Support promoting proposed ADRs to `accepted/` or scaffolding new amending ADR files.
2. **CLI Workflow**:
   - Register `spec-ops adr amend` subcommand in `src/spec_ops/cli/parser_adr.py` and handle dispatch in `src/spec_ops/cli/adr_handler.py`.
3. **DoR Gate & Reconciler Protection**:
   - In `src/spec_ops/backlog/dor_gate.py` and `src/spec_ops/backlog/dor.py`, verify tasks citing amended ADRs pass the governing ADR gate cleanly.
   - In `src/spec_ops/backlog/reconciler.py`, ensure amended ADRs are never treated as superseded.
4. **Testing**:
   - BDD scenarios in `tests/features/us_0130_adr_amendment.feature` and `tests/test_bdd_us0130_adr_amendment.py`.
   - Unit tests and Hypothesis property tests for cycle detection.

## Definition of Done
1. `spec-ops adr amend <old-id> --title <title>` scaffolds new ADR with `amends: [<old-id>]` and updates target ADR with `amended_by: [<new-id>]`.
2. Target ADR remains `Accepted` and REGISTRY.md is synchronized without marking it Superseded.
3. Circular amendments raise `CircularAmendmentError` and leave files unmodified.
4. Tasks citing amended ADRs pass DoR gates without reconciler replacement.
5. 100% test pass rate with 0 file limit violations (<500 lines) and 0 warnings (<400 lines).
