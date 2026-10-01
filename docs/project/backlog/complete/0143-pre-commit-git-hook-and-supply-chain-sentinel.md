---
id: '0143'
title: Automated Pre-Commit Git Hook Installer and Supply-Chain Sentinel
status: Complete
dependencies:
- TASK-0127
- TASK-0130
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0018
- ADR-0019
governing_prds:
- PRD-0002
governing_stories:
- US-0054
- US-0055
target_bc: security
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T11:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0143: Automated Pre-Commit Git Hook Installer and Supply-Chain Sentinel

## Summary
Implement automated pre-commit hook installation and real-time supply-chain enforcement (`spec-ops security hook install [--uninstall] [--verify]`). Governed by ADR-0018 and ADR-0019, this engine installs git pre-commit hooks that intercept staged commits, preventing unauthorized lockfile drift (`uv.lock`), secret leaks, and oversized file commits prior to git commit finalization.

## Problem Statement & Context
While CI/CD and worktree preflight checks catch supply-chain tampering and credential leaks before merge, local commits on developer or agent machines can inadvertently stage secrets or modified lockfiles into git history. Cleaning git history post-commit is complex. Installing automated pre-commit hooks provides real-time, local defense-in-depth at the point of commit creation.

## Key Requirements & Scope
1. **Hook Management Engine (`src/spec_ops/security/git_hooks.py`)**:
   - Installs `.git/hooks/pre-commit` script invoking `spec-ops health --security` and lockfile checks.
   - Preserves existing pre-commit hooks or integrates seamlessly into existing hook chains.
2. **Real-Time Sentinel Execution**:
   - Rejects commits containing unapproved `uv.lock` modifications (ADR-0018).
   - Rejects commits containing high-entropy tokens or credentials (ADR-0019).
   - Rejects commits introducing files over the 500-line threshold (ADR-0002).
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Hook engine in `src/spec_ops/security/git_hooks.py` must stay strictly under 400 lines (ADR-0002).
- **Supply-Chain Integrity (ADR-0018, ADR-0019)**: Lockfile drift and credential leaks are blocked prior to commit creation.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/security/git_hooks.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Installing pre-commit hook in git repository
```gherkin
Given an initialized SpecOps repository
When the user runs "spec-ops security hook install"
Then a pre-commit executable is created in ".git/hooks/pre-commit"
And the hook invokes security and lockfile verification checks
```

### Scenario 2: Blocking commits with unapproved lockfile drift
```gherkin
Given an active pre-commit hook installed
When a commit stages an unapproved change to "uv.lock"
Then the pre-commit hook exits with code 1
And the git commit is aborted
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that hook generation, installation, and removal roundtrips cleanly without corrupting existing shell scripts or leaving orphaned temporary files.
