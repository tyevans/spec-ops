---
id: '0140'
title: Zero-Trust Autonomous Worker Process Sandboxing and Environment Scrubbing
status: Complete
dependencies:
- TASK-0051
- TASK-0114
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0012
governing_prds:
- PRD-0004
governing_stories:
- US-0027
- US-0028
target_bc: worker
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T11:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0140: Zero-Trust Autonomous Worker Process Sandboxing and Environment Scrubbing

## Summary
Implement zero-trust process isolation and environment variable scrubbing for autonomous worker executions (`src/spec_ops/worker/sandbox_env.py`). Governed by ADR-0012, this engine strips sensitive environment credentials (e.g. cloud tokens, API keys, private SSH variables) prior to launching worker subshells in worktrees, and limits child process execution to allowlisted toolchain binaries.

## Problem Statement & Context
Autonomous coding agents operating in git worktrees execute shell commands and tests. If the parent environment contains ambient developer secrets (e.g. `AWS_SECRET_ACCESS_KEY`, `GITHUB_TOKEN`, private tokens), errant or untrusted code executed during preflight or build steps could leak sensitive credentials. ADR-0012 mandates defense-in-depth process sandboxing with deterministic environment sanitization.

## Key Requirements & Scope
1. **Environment Scrubbing (`src/spec_ops/worker/sandbox_env.py`)**:
   - Strips environment variables matching high-entropy secret patterns or sensitive prefixes (`AWS_`, `GITHUB_`, `OPENAI_`, `TOKEN`, `KEY`, `SECRET`, `PASSWORD`).
   - Retains only explicit toolchain allowlists (`PATH`, `HOME`, `USER`, `LANG`, `TERM`, `VIRTUAL_ENV`).
2. **Process Execution Guardrails**:
   - Restricts child process execution to approved command prefixes (`uv`, `git`, `python`, `pytest`, `spec-ops`).
   - Injects configurable execution timeouts and memory limit caps.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Sandboxing module in `src/spec_ops/worker/sandbox_env.py` must stay strictly under 400 lines (ADR-0002).
- **Security Invariant (ADR-0012)**: Ambient environment secrets must never propagate into child worker executions.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/worker/sandbox_env.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Scrubbing sensitive environment variables before worker spawn
```gherkin
Given an ambient parent environment containing "AWS_SECRET_ACCESS_KEY" and "GITHUB_TOKEN"
When the worker sandbox sanitizes the execution environment
Then the resulting worker environment dictionary contains only allowlisted variables
And all high-entropy secret variables are stripped
```

### Scenario 2: Blocking non-allowlisted command execution in sandboxed worktree
```gherkin
Given a sandboxed worker runner
When an attempt is made to execute an unapproved binary outside the allowlist
Then the execution is rejected with a security violation error
And zero subprocesses are spawned
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary dictionary of environment key-value pairs, sanitization deterministically filters out sensitive keys and retains exclusively allowlisted entries without throwing exceptions.
