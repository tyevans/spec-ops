---
id: '0021'
title: Diataxis Documentation Drift Auditor and Validator
status: Complete
dependencies:
- TASK-0015
governing_adrs:
- ADR-0008
governing_prds:
- PRD-0001
governing_stories:
- US-0008
target_bc: core
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0021: Diataxis Documentation Drift Auditor and Validator

## Summary
Implement a documentation drift audit command (`spec-ops docs audit`) that validates Diataxis quadrant compliance, verifies CLI reference specs against actual command parsers, and tests code snippets in documentation.

## Problem Statement
As code evolves, CLI arguments, configuration models, and architectural patterns drift from existing Diataxis documentation without warning. Developers and agents need an automated verification mechanism to ensure docs remain 100% accurate.

## Detailed Objectives
1. **Diataxis Structure Validation**:
   - Verify that all files under `docs/` reside within approved quadrants (`tutorials/`, `how-to/`, `reference/`, `explanation/`, `project/`).
2. **CLI & Model Drift Verification**:
   - Compare `docs/reference/cli.md` against actual arguments defined in `argparse` / `main.py`.
   - Flag any missing or extra options.
3. **Markdown Code Snippet Testing**:
   - Validate that python and bash snippets in documentation pass syntax checks and run cleanly where applicable.

## Definition of Done (Blackbox Frontdoor TDD)
1. `spec-ops docs audit` command implemented and verified through CLI tests.
2. Reports any missing Diataxis quadrant docs or CLI flag drift.
3. Zero files exceed 500 lines.
