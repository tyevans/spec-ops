---
id: '0030'
title: Cryptographic Commit Verification and Dual-Custody Gate
status: Complete
dependencies:
- TASK-0024
- TASK-0028
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0005
governing_prds:
- PRD-0002
governing_stories:
- US-0055
- US-0113
target_bc: security
allows_dependencies: true
---

# TASK-0030: Cryptographic Commit Verification and Dual-Custody Gate

## Summary
Implement GPG/SSH commit signature verification and mandatory human dual-custody review sign-offs for autonomous agent tasks. Add CLI command `spec-ops review sign <task-id> --identity <key-id>` to verify reviewer signatures against the keyring, record `signed_off_by` and timestamps in task frontmatter, inject structured `SpecOps-Signed-By` git trailers, and gate `spec-ops queue complete` when `require_signed_commits = true`.

## Problem Statement & Context
Regulatory compliance frameworks (SOC2 Type II CC8.1, ISO 27001 A.12.1.2) mandate that autonomous AI agents cannot unilaterally merge modifications into production branches without verified dual control and human sign-off. Every commit must have provable, non-repudiable cryptographic signatures, and every autonomous agent task must be formally signed off by an authorized human architect before integration into `main`.

## User Stories & Scenarios Satisfied
- **US-0055: Cryptographic Commit Verification and Dual-Custody Human Sign-Off Gate**
  - *Scenario*: Blocking integration of unsigned git commits into main
  - *Scenario*: Enforcing dual-custody human review sign-off
- **US-0113: Cryptographic Commit Verification and Dual-Custody Human Sign-Off Gate**
  - *Scenario*: Blocking integration of unsigned git commits into main
  - *Scenario*: Enforcing dual-custody human review sign-off on autonomous agent tasks
  - *Scenario*: Recording verified human reviewer signature into task metadata and git commit

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Modularize signing and dual-custody logic into `src/spec_ops/security/signing.py` and `src/spec_ops/security/dual_custody.py`, maintaining strict line limits (<400 lines) per module (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` verify git trailer parsing, commit message formatting, and key ID validation across arbitrary commit messages with varying whitespace and multiline trailers.
- **Mutmut Mutation Scope**: Signature verification and human sign-off gating in `src/spec_ops/security/signing.py` and `src/spec_ops/security/dual_custody.py` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. When `require_signed_commits = true` is configured in `[security.compliance]`, executing `spec-ops queue complete <task-id>` or worker merge on a branch with unsigned commits aborts with returncode 1 and diagnostic message "Compliance Violation: Commit <sha> lacks valid cryptographic signature (GPG/SSH)".
2. Autonomous agent tasks lacking human approval are blocked from transitioning to `complete/` with actionable prompt guidance to run `spec-ops review sign <task-id> --identity <key-id>`.
3. Executing `spec-ops review sign <task-id> --identity <key-id>` verifies the identity against authorized signers, updates task frontmatter with `signed_off_by: <reviewer>`, and writes sign-off timestamps.
4. Subsequent execution of `spec-ops queue complete <task-id>` merges cleanly to `main` with structured `SpecOps-Signed-By` git trailers.
5. All scenarios verified via executable `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
