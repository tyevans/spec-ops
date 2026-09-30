---
id: '0024'
title: Security Profile Scaffolding and Living Constitution Guardrails
status: Complete
dependencies:
- TASK-0003
- TASK-0010
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0008
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


# TASK-0024: Security Profile Scaffolding and Living Constitution Guardrails

## Summary
Implement the `security` architectural profile for `spec-ops init --profile security` and `spec-ops profile apply security`. Scaffold baseline security ADRs, Diataxis-compliant vulnerability disclosure policy `docs/project/SECURITY.md`, `specops.toml` `[security]` configuration, and non-negotiable security invariants dynamically injected into `AGENTS.md`. Add `spec-ops health --security` check for degraded security policies.

## Problem Statement & Context
When setting up new repositories or managing enterprise brownfield codebases, security guardrails are often omitted or authored as static documentation that autonomous agents ignore. Without automated security profile scaffolding, autonomous agents operate without constitutional constraints, risking secret exposure, unvetted dependencies, and unconstrained execution. Security directives must be version-locked as machine-executable constitutional rules and configuration blocks from day zero.

## User Stories & Scenarios Satisfied
- **US-0051: Enterprise Security and Compliance Profile Scaffolding**
  - *Scenario*: Scaffolding a repository with the security architectural profile
  - *Scenario*: Dynamic injection of security invariants into AGENTS.md
- **US-0108: Enterprise Security Profile Scaffolding and Living Constitution Guardrails**
  - *Scenario*: Scaffolding a repository with the security architectural profile
  - *Scenario*: Dynamic injection of security invariants into AGENTS.md
  - *Scenario*: Preflight detection of degraded or missing security configuration

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Profile generator modules in `src/spec_ops/profiles/security.py` and scaffolding extensions in `src/spec_ops/scaffold/` remain strictly modular and well below 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property tests using `@given(...)` across permutations of profile selections (`core`, `bdd`, `ddd`, `security`) verify that generated `AGENTS.md` and `specops.toml` files deterministically contain valid, non-overlapping sections without syntax corruption.
- **Mutmut Mutation Scope**: Core profile generation logic in `src/spec_ops/profiles/security.py` achieves >=80% mutant kill score, ensuring configuration validation and mandatory text presence assertions cannot be silently removed.

## Definition of Done (Blackbox Frontdoor TDD)
1. Executing `spec-ops init --name SecureApp --profile core,bdd,security` scaffolds baseline security ADRs under `docs/project/adrs/accepted/`, generates `docs/project/SECURITY.md` with vulnerability reporting workflows, and configures `[security]` in `specops.toml`.
2. Executing `spec-ops scaffold agents` injects a non-negotiable "Security & Supply-Chain Hard Invariants" section into `AGENTS.md` forbidding hardcoded credentials, unapproved lockfiles, and non-allowlisted shell commands.
3. Executing `spec-ops health --security` exits with returncode 1 when `docs/project/SECURITY.md` or required configuration blocks are missing or modified out-of-spec, providing actionable restoration guidance.
4. All acceptance criteria verified via blackbox `pytest-bdd` scenarios without private mock backdoors (ADR-0003, ADR-0006).
