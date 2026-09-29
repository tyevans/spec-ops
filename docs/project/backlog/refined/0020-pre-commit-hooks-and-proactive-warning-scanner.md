---
id: '0020'
title: Git Pre-Commit Hook Scaffolding and Proactive Invariant Warnings
status: Refined
dependencies:
- TASK-0005
governing_adrs:
- ADR-0002
governing_prds:
- PRD-0001
governing_stories:
- US-0002
target_bc: backlog
---

# TASK-0020: Git Pre-Commit Hook Scaffolding and Proactive Invariant Warnings

## Summary
Add pre-commit hook scaffolding to `spec-ops init` and enhance `spec-ops health` with a proactive warning threshold (e.g., >400 lines) to alert developers before files breach the 500-line limit.

## Problem Statement
Currently, `spec-ops health` only flags files after they exceed 500 lines. This forces emergency refactoring halts during active feature development. Additionally, human engineers (Riley) lack automatic git hook integration to catch violations before `git commit`.

## Detailed Objectives
1. **Proactive Refactoring Warnings**:
   - Update `HealthChecker` to output warning notifications for source files between 400 and 500 lines.
   - List top largest files approaching the limit to guide preemptive decomposition.
2. **Pre-commit Hook Scaffolding**:
   - Add `.pre-commit-config.yaml` template generation to `spec_ops.scaffold`.
   - Wire `spec-ops health` and Ruff into local pre-commit hooks during `spec-ops init`.

## Definition of Done (Blackbox Frontdoor TDD)
1. `spec-ops health` reports both hard violations (>500 lines) and proactive warnings (>400 lines).
2. `spec-ops init` scaffolds `.pre-commit-config.yaml` with passing hook validation.
3. Tests verify hook configuration and warning thresholds.
