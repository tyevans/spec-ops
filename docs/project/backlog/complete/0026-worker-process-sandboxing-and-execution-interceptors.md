---
id: '0026'
title: Hardened Worker Process Sandboxing and Network Egress Interceptor
status: Complete
dependencies:
- TASK-0011
- TASK-0025
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0007
governing_prds:
- PRD-0002
governing_stories:
- US-0054
- US-0109
target_bc: security
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0026: Hardened Worker Process Sandboxing and Network Egress Interceptor

## Summary
Implement production worker process sandboxing and command execution interception inside `spec-ops worker` governed by ADR-0010. Enforce `[execution.sandbox] allowed_commands`, block prohibited utilities (`curl`, `wget`, `sudo`, `rm -rf /`) with exit code 126, write structured audit events to `.worktrees/<task-id>/.security-audit.log`, and implement socket-level network egress blocking when `isolate_network = true`.

## Problem Statement & Context
Autonomous agent execution sessions must operate within strict containment boundaries. While agents need full access to project toolchains (`uv`, `git`, `pytest`, `ruff`), they must be technically prevented from modifying the host system, running unauthorized subshells, escalating privileges, or communicating with external IP addresses during test preflight and execution.

## User Stories & Scenarios Satisfied
- **US-0054: Autonomous Worker Process Sandboxing and Shell Command Allowlisting**
  - *Scenario*: Intercepting and terminating forbidden shell commands
  - *Scenario*: Network isolation during test verification
- **US-0109: Autonomous Worker Process Sandboxing and Shell Command Execution Interceptors**
  - *Scenario*: Intercepting and terminating forbidden shell commands in worker worktrees
  - *Scenario*: Enforcing network isolation during preflight test execution
  - *Scenario*: Seamless execution of allowlisted developer toolchain

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Decompose into single-responsibility modules: `src/spec_ops/security/sandbox.py`, `src/spec_ops/security/interceptor.py`, and `src/spec_ops/security/network_guard.py`, each under 400 lines (ADR-0002).
- **Hypothesis Invariant Property (ADR-0009)**: Generative property testing using `@given(st.lists(st.text()))` verifies that any command execution attempting non-allowlisted binaries consistently terminates with exit code 126 and writes an audit event, regardless of arguments or chaining.
- **Mutmut Mutation Scope**: Execution guards and audit event logging logic in `src/spec_ops/security/interceptor.py` maintain >=80% mutant kill score under `mutmut`.

## Definition of Done (Blackbox Frontdoor TDD)
1. `spec-ops worker execute <task-id>` enforces `allowed_commands = ["uv", "git", "pytest", "ruff"]` configured in `specops.toml`.
2. Prohibited utilities (e.g. `curl`, `wget`, `sudo`, `rm -rf /`) are intercepted and terminated with exit code 126 (Command Prohibited), outputting diagnostic error details.
3. Every prohibited command attempt writes a structured JSON record (command, timestamp, parent PID) to `.worktrees/<task-id>/.security-audit.log`.
4. When `isolate_network = true`, attempts to open outbound network sockets to non-loopback addresses during preflight verification fail cleanly as architectural boundary violations.
5. Allowlisted commands (`uv run pytest`, `git status`) execute without latency degradation (<5ms overhead) or stream truncation.
6. Acceptance verified via executable `pytest-bdd` tests without private mock backdoors (ADR-0003, ADR-0006).
