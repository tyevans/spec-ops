---
id: '0027'
title: Worktree Diff Secret and High-Entropy Credential Detection Engine
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0024
governing_adrs:
  - ADR-0001
  - ADR-0002
  - ADR-0003
  - ADR-0004
governing_prds:
  - PRD-0002
governing_stories:
  - US-0052
  - US-0110
target_bc: security
---

# TASK-0027: Worktree Diff Secret and High-Entropy Credential Detection Engine

## Summary
Implement real-time credential and secret leak detection scanning for unstaged, staged, and branch worktree diffs via `spec-ops health --security` and autonomous worker preflight verification. Combine Shannon entropy analysis with signature patterns for SaaS tokens, API keys (OpenAI, AWS, GitHub, Slack), and cryptographic private keys. Block commits containing exposed secrets or tracked sensitive dotfiles (`.env`, `.env.production`, `id_rsa`) with masked diagnostic self-healing feedback.

## Problem Statement & Context
Autonomous coding agents and human engineers occasionally hardcode credentials, private tokens, or copy-paste `.env` configuration files into source files. Once committed into git history, emergency key revocations, upstream credential rotation, and destructive git history scrubbing (`git-filter-repo`) are required. Detecting leaks in real-time inside the worktree diff *before* commits are generated stops leaks at the point of origin.

## User Stories & Scenarios Satisfied
- **US-0052: Automated Secret and Credential Leak Detection in Agent Worktrees**
  - *Scenario*: Blocking commits containing high-entropy secrets or private tokens
  - *Scenario*: Clean worktree passes preflight credential scan
- **US-0110: Real-Time Secret and High-Entropy Credential Detection in Worktree Diffs**
  - *Scenario*: Blocking commits containing high-entropy secrets or private tokens
  - *Scenario*: Blocking inclusion of unignored sensitive dotfiles in git tracking
  - *Scenario*: Clean worktree passes preflight credential scan

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Modularize scanner components into `src/spec_ops/security/secrets/scanner.py`, `src/spec_ops/security/secrets/entropy.py`, and `src/spec_ops/security/secrets/patterns.py`, ensuring all modules remain well under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property testing using `@given(st.text())` verifies mathematical entropy bounds (`0.0 <= entropy <= 8.0`) and non-crashing behavior across arbitrary binary, null byte, and unicode text streams.
- **Mutmut Mutation Scope**: Token patterns, Shannon entropy threshold checks, and string masking functions in `src/spec_ops/security/secrets/` achieve >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. `spec-ops health --security` scans worktree diffs and exits with returncode 1 when high-entropy credentials or sensitive private keys are detected.
2. Aborted preflight outputs actionable diagnostic feedback containing the file path, line number, and safely masked token snippet (e.g., `sk-proj-****4x9Z`) enabling agent self-healing.
3. Attempting to track sensitive dotfiles (`.env`, `.env.production`, `id_rsa`) aborts commit preflight with instructions to update `.gitignore`.
4. Clean worktrees referencing secrets strictly through environment variables pass with returncode 0 and report "Security Invariant Met: 0 credential leaks detected".
5. All scenarios verified via executable `pytest-bdd` acceptance tests through public CLI frontdoors with zero mock backdoors (ADR-0003, ADR-0006).
