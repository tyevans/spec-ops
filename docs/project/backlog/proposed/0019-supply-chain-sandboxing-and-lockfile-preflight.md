---
id: '0019'
title: Supply-Chain Sandboxing and Lockfile Preflight Enforcement
status: Proposed
created: 2026-09-29
dependencies:
  - TASK-0011
governing_adrs:
  - ADR-0001
  - ADR-0004
governing_prds:
  - PRD-0001
governing_stories:
  - US-0005
target_bc: core
---

# TASK-0019: Supply-Chain Sandboxing and Lockfile Preflight Enforcement

## Summary
Incorporate dependency lockfile verification (`uv lock --check`) into default preflight gates and define execution sandboxing boundaries for autonomous agent sessions to satisfy security requirements (Sasha).

## Problem Statement
Autonomous coding agents executing arbitrary shell commands can unintentionally introduce hallucinated third-party dependencies ("slopsquatting") or execute commands outside the intended worktree context. Additionally, changes to `pyproject.toml` without synchronizing `uv.lock` can break downstream builds.

## Detailed Objectives
1. **Preflight Lockfile Gate**:
   - Add `uv lock --check` to default quality preflight checks in `SpecOpsConfig`.
   - Ensure any modified dependency graph is verified for consistency and absence of unverified packages.
2. **Execution Environment Sandboxing**:
   - Isolate autonomous worker subshells to restrict ambient directory traversal outside `.worktrees/<task-id>`.
   - Prevent execution of unsandboxed root privilege or dangerous network operations.
3. **Audit Provenance Logging**:
   - Record commit metadata containing agent session IDs, prompt hashes, and timestamp logs for verifiable compliance.

## Definition of Done (Blackbox Frontdoor TDD)
1. Preflight verifies lockfile consistency and blocks tasks with desynchronized lockfiles.
2. Integration tests verify worker execution logs metadata and prevents directory escape.
3. Zero files exceed 500 lines.
