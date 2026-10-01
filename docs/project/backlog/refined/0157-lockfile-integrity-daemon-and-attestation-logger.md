---
id: '0157'
title: Incremental Lockfile Integrity Daemon and Supply-Chain Attestation Logger
status: Refined
dependencies:
- TASK-0028
- TASK-0127
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0010
- ADR-0018
governing_prds:
- PRD-0002
governing_stories:
- US-0111
target_bc: security
---

# TASK-0157: Incremental Lockfile Integrity Daemon and Supply-Chain Attestation Logger

## Summary
Implement an incremental supply-chain lockfile integrity sentinel and attestation audit logger (`src/spec_ops/security/supply_chain_daemon.py`). Governed by ADR-0018 and PRD-0002, this engine computes cryptographic SHA-256 rolling digests over root lockfiles (`uv.lock`), monitors file system changes in real-time, and records tamper-evident attestation logs into an audit ledger (`spec-ops security audit-lockfile`).

## Problem Statement & Context
Autonomous agent swarms executing in parallel worktrees may inadvertently alter dependency graph lockfiles or pull unapproved transitive packages. While preflight checks intercept changes at commit time, an incremental background integrity auditor catches unauthorized tampering in real-time, preventing slopsquatting attacks before code execution proceeds.

## Key Requirements & Scope
1. **Lockfile Integrity Sentinel (`src/spec_ops/security/supply_chain_daemon.py`)**:
   - Calculates canonical SHA-256 digests over `uv.lock` and `pyproject.toml`.
   - Validates package source URLs against allowed PyPI repository indexes.
   - Detects unexpected dependency modifications or newly introduced unpinned packages.
   - Generates structured tamper-evident attestation records with timestamps and cryptographic signatures.
2. **Lockfile Audit CLI (`spec-ops security audit-lockfile [--verify] [--json] [--record]`)**:
   - Compares the active lockfile against the recorded baseline attestation.
   - Exits with code 0 if integrity is intact, or code 1 with detailed discrepancy analysis if tampering is detected.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Sentinel module in `src/spec_ops/security/supply_chain_daemon.py` must stay strictly under 400 lines (ADR-0002).
- **Lockfile Immutability (ADR-0018)**: Zero unapproved modifications to `uv.lock`.
- **Mutation Testing Scope**: Target module `src/spec_ops/security/supply_chain_daemon.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Verifying authentic lockfile integrity
```gherkin
Given a verified repository with an intact uv.lock file
When the security lockfile auditor runs verification
Then the calculated digest matches the recorded attestation
And the command exits with status 0
```

### Scenario 2: Detecting unauthorized lockfile tampering
```gherkin
Given a lockfile modified with unauthorized dependency alterations
When the security lockfile auditor runs verification
Then the discrepancy is flagged as an unauthorized supply-chain modification
And the command terminates with exit code 1
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that any single-byte alteration to lockfile text produces a distinct SHA-256 digest and causes verification to fail deterministically.
