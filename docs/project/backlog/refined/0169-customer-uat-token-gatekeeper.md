---
id: 0169
title: Customer UAT Sign-Off Cryptographic Token Exporter and Release Gatekeeper
status: Refined
dependencies:
- TASK-0041
- TASK-0126
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0014
- ADR-0016
governing_prds:
- PRD-0003
governing_stories:
- US-0100
target_bc: prd
---

# TASK-0169: Customer UAT Sign-Off Cryptographic Token Exporter and Release Gatekeeper

## Summary
Implement a customer UAT sign-off token generator and automated release gatekeeper (`src/spec_ops/prd/uat_gatekeeper.py`). Governed by ADR-0014 and PRD-0003, this engine verifies that all customer checkable outcomes in target PRDs have verified UAT sign-off tokens and cryptographic attestations before allowing release tags or production build generation (`spec-ops prd gate`).

## Problem Statement & Context
Shipping releases without verifiable customer sign-off or with incomplete acceptance criteria creates significant business and compliance risk. Even when automated unit tests pass, customer acceptance verification must be provably satisfied. An automated release gatekeeper verifies cryptographic UAT tokens and ensures zero untested checkable outcomes slip into production releases.

## Key Requirements & Scope
1. **UAT Gatekeeper Engine (`src/spec_ops/prd/uat_gatekeeper.py`)**:
   - Parses target PRD documents and extracts all checkable outcomes.
   - Verifies cryptographic UAT receipt tokens (`.specops/uat_receipts/` or embedded manifest).
   - Validates that authorized customer identities signed off on every checkable criterion.
   - Computes release readiness score and identifies blocking unverified outcomes.
2. **Release Gate CLI (`spec-ops prd gate --prd <PRD_ID> [--strict] [--json]`)**:
   - Evaluates UAT readiness and outputs a release sign-off decision (PASS / BLOCKED).
   - Exits with code 0 on full sign-off, or code 1 if unverified criteria block release.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Module in `src/spec_ops/prd/uat_gatekeeper.py` must stay strictly under 400 lines (ADR-0002).
- **Tamper-Evident Receipts (ADR-0014)**: Verification requires authentic cryptographic UAT signatures.
- **Mutation Testing Scope**: Target module `src/spec_ops/prd/uat_gatekeeper.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Authorizing release when all checkable outcomes have verified UAT receipts
```gherkin
Given a PRD where 100% of checkable outcomes possess valid cryptographic UAT receipts
When the gatekeeper evaluates release readiness
Then the release gate returns PASS with verification details
And the command terminates with exit code 0
```

### Scenario 2: Blocking release when unverified checkable outcomes remain
```gherkin
Given a PRD containing unverified checkable outcomes
When the gatekeeper evaluates release readiness with strict mode
Then the unverified criteria are listed as release blockers
And the command terminates with exit code 1
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that any UAT verification decision is purely a deterministic function of outcome check states and signature validity without side effects.
