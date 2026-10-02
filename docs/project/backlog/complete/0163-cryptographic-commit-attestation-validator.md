---
id: '0163'
title: Cryptographic Commit Attestation and Sigstore Keyring Validator
status: Complete
dependencies:
- TASK-0030
- TASK-0149
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0014
- ADR-0016
governing_prds:
- PRD-0002
governing_stories:
- US-0113
target_bc: security
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-02T00:47:14.481056+00:00'
commit_signature_status: SIGNED
has_signed_commits: true
---

# TASK-0163: Cryptographic Commit Attestation and Sigstore Keyring Validator

## Summary
Implement a cryptographic commit attestation and public key signature chain validator (`src/spec_ops/security/commit_attestation.py`). Governed by ADR-0014 and PRD-0002, this engine validates git commit signatures (GPG, SSH, or Sigstore cosign signatures) across task branch ranges and pull requests against authorized keyring entries (`spec-ops security verify-commits`).

## Problem Statement & Context
Autonomous agent worktrees and human contributors collaborate on shared repositories. To prevent commit spoofing and unauthorized branch insertions, every commit integrated into `main` must carry an authentic cryptographic signature verified against authorized maintainer and agent keyrings.

## Key Requirements & Scope
1. **Commit Attestation Engine (`src/spec_ops/security/commit_attestation.py`)**:
   - Inspects git commit objects and extracts raw commit buffer and signature payloads.
   - Verifies SSH Ed25519 signatures and GPG signatures against `.allowed_signers` or configured keyring.
   - Validates that commit author and committer identities correspond to the signing public key.
   - Evaluates commit ranges (`HEAD~N..HEAD` or `origin/main..HEAD`).
2. **Commit Verification CLI (`spec-ops security verify-commits [--range <rev-range>] [--keyring <path>] [--strict] [--json]`)**:
   - Analyzes commit signatures in the specified range.
   - Exits with code 0 on verified signature chains, or code 1 if unsigned or unverified commits are found.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Module in `src/spec_ops/security/commit_attestation.py` must stay strictly under 400 lines (ADR-0002).
- **Cryptographic Release Verification (ADR-0014)**: Leverages pure Edwards25519 and standard verification interfaces.
- **Mutation Testing Scope**: Target module `src/spec_ops/security/commit_attestation.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Verifying authentically signed commit ranges
```gherkin
Given a git branch containing cryptographically signed commits
And an authorized keyring containing the signer public key
When the developer runs spec-ops security verify-commits
Then all commits in the range are verified
And the command terminates with exit code 0
```

### Scenario 2: Rejecting unsigned or forged commits in branch
```gherkin
Given a branch containing an unsigned commit
When the developer runs spec-ops security verify-commits with strict mode
Then the unsigned commit is flagged
And the command exits with error status 1
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that any malformed commit header or corrupted signature payload is safely handled without raising unhandled exceptions.
