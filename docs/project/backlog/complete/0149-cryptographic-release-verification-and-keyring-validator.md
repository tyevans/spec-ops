---
id: 0149
title: Cryptographic Release Verification and Public Keyring Validator
status: Complete
dependencies:
- TASK-0126
- TASK-0141
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0014
governing_prds:
- PRD-0002
governing_stories:
- US-0055
- US-0056
target_bc: security
---

# TASK-0149: Cryptographic Release Verification and Public Keyring Validator

## Summary
Implement the cryptographic release verification and public keyring validation engine (`spec-ops release verify --manifest <path> [--keyring <path>]`). Governed by ADR-0014 and PRD-0002, this engine validates customer UAT receipts, release manifest Merkle roots, and Ed25519 digital signatures against authorized signer keys in `.allowed_signers` without external dependencies.

## Problem Statement & Context
Customer acceptance signoffs and cryptographic release manifests protect software deliverables from tampering. However, clients and automated deployment pipelines need a standardized CLI and library interface to verify that release signatures and Merkle trees are authentic and signed by authorized key holders before deployment.

## Key Requirements & Scope
1. **Keyring and Signature Validator (`src/spec_ops/security/release_verifier.py`)**:
   - Parses `.allowed_signers` and OpenSSH-format Ed25519 public keys.
   - Validates release manifest signatures, tree digests, and UAT receipt tokens.
   - Emits structured verification reports with exit code 0 on valid signature or 1 on counterfeit/tampered manifests.
2. **Release Verification CLI (`spec-ops release verify`)**:
   - Accepts `--manifest <path>`, `--keyring <path>`, `--strict`, and `--json`.
   - Validates that every mandatory customer outcome is signed and tamper-free.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Release verifier module in `src/spec_ops/security/release_verifier.py` must stay strictly under 400 lines (ADR-0002).
- **Zero-Dependency Cryptographic Verification (ADR-0014)**: Verification operates locally without external trust anchors or network daemons.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/security/release_verifier.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Verifying valid cryptographic release manifest
```gherkin
Given a release manifest signed by an authorized key in ".allowed_signers"
When the auditor executes "spec-ops release verify --manifest release-manifest.json"
Then the verification succeeds with exit code 0
And the report confirms cryptographic validity and signer identity
```

### Scenario 2: Rejecting tampered release manifest
```gherkin
Given a release manifest whose payload has been modified post-signing
When the auditor executes "spec-ops release verify --manifest release-manifest.json"
Then the verification fails with exit code 1
And identifies the signature mismatch error
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary key pair and signed payload, verification returns True if and only if the payload and signature match the authentic public key.
