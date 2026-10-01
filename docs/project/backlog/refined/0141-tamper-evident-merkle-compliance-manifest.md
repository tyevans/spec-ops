---
id: '0141'
title: Tamper-Evident Merkle Tree Compliance Manifest Generator
status: Refined
dependencies:
- TASK-0056
- TASK-0129
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0016
governing_prds:
- PRD-0002
governing_stories:
- US-0056
- US-0057
target_bc: security
---

# TASK-0141: Tamper-Evident Merkle Tree Compliance Manifest Generator

## Summary
Implement the cryptographic Merkle tree compliance manifest generator (`spec-ops audit merkle [--verify] [--output <path>]`). Governed by ADR-0016 and PRD-0002, this engine hashes all PMaC specification files (`docs/project/`) and source code files into a deterministic Merkle tree, emitting a root digest and tamper-evident audit receipt for customer and regulatory compliance verification.

## Problem Statement & Context
Regulated enterprise customers and security auditors require cryptographic proof that software specifications and implementation files have not been modified post-approval. Storing individual file SHA-256 hashes is cumbersome for audit verification. ADR-0016 specifies a hierarchical Merkle tree structure where any single leaf file modification alters the root digest, enabling sub-millisecond tamper verification across the entire project repository.

## Key Requirements & Scope
1. **Deterministic Merkle Tree Engine (`src/spec_ops/security/merkle_manifest.py`)**:
   - Computes SHA-256 leaf digests for all version-locked artifacts in `docs/project/` and `src/`.
   - Constructs a balanced binary Merkle tree with sorted deterministic branch ordering.
   - Generates inclusion proofs for individual specification files.
2. **Audit Verification CLI**:
   - `spec-ops audit merkle` outputs root hash and tree statistics.
   - `spec-ops audit merkle --verify <manifest.json>` verifies that the current repository state matches the cryptographic root digest.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Merkle manifest module in `src/spec_ops/security/merkle_manifest.py` must stay strictly under 400 lines (ADR-0002).
- **Cryptographic Tamper Invariant (ADR-0016)**: Modifying any single byte in any specification or source file produces a distinct root Merkle digest.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/security/merkle_manifest.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Generating deterministic Merkle root digest for project repository
```gherkin
Given a project repository with accepted PRDs, ADRs, and tasks
When the auditor runs "spec-ops audit merkle"
Then a deterministic Merkle root hash is generated
And each leaf node corresponds to a version-controlled specification or source artifact
```

### Scenario 2: Detecting unauthorized file tampering via Merkle verification
```gherkin
Given a verified Merkle compliance manifest
When a file in "docs/project/" is modified without updating the manifest
Then running "spec-ops audit merkle --verify manifest.json" detects a digest mismatch
And identifies the exact tampered file path
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary set of file paths and file contents, Merkle tree construction is deterministic, order-independent, and leaf mutation alters the root hash.
