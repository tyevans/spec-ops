# Merkle Compliance Manifest Reference

SpecOps provides a mathematically verifiable, tamper-evident audit manifest data structure governed by [ADR-0016](../project/adrs/accepted/adr-0016-tamper-evident-merkle-compliance-manifests.md).

---

## Overview

Enterprise compliance frameworks (SOC2 Type II, ISO 27001 Annex A) require continuous proof of SDLC traceability:
$$\text{PRD} \longrightarrow \text{User Story} \longrightarrow \text{Task} \longrightarrow \text{Agent Prompt} \longrightarrow \text{Commit SHA} \longrightarrow \text{Test Results} \longrightarrow \text{Human Review}$$

SpecOps compiles completed deliverables into a power-of-2 binary Merkle tree, generating a top-level SHA-256 root digest and enabling $O(\log N)$ inclusion proofs for individual deliverables.

---

## Cryptographic Invariants

### 1. Canonical Serialization (RFC 8785)
All entity payloads are serialized with strict JSON Canonicalization Scheme (JCS) before hashing:
- Lexicographical UTF-16 code unit key sorting (`key.encode("utf-16-be")`).
- Compact token formatting without extraneous whitespace (`separators=(",", ":")`).
- Unescaped UTF-8 string encoding (`ensure_ascii=False`).

### 2. Domain Separation Hashing (RFC 6962)
To eliminate second-preimage attacks and node confusion vulnerabilities:
- **Leaf Nodes**: $\text{LeafHash} = \text{SHA-256}(0\text{x}00 \mathbin{\Vert} \text{JCS}(\text{DeliverableData}))$
- **Internal Nodes**: $\text{NodeHash} = \text{SHA-256}(0\text{x}01 \mathbin{\Vert} \text{LeftChildHash} \mathbin{\Vert} \text{RightChildHash})$
- **Empty Tree Root**: $\text{Root}(\emptyset) = \text{SHA-256}(\text{""})$ (`e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855`)

### 3. Tree Split Calculation
For a sequence of $N$ deliverables sorted deterministically by canonical `task_id`:
- If $N = 0$: Return empty root hash.
- If $N = 1$: Return leaf hash.
- If $N > 1$: Split at $k = 2^{\lfloor \log_2(N-1) \rfloor}$ (largest power of 2 strictly less than $N$):
  $$\text{Root} = \text{SHA-256}(0\text{x}01 \mathbin{\Vert} \text{MTH}(D[0:k]) \mathbin{\Vert} \text{MTH}(D[k:N]))$$

---

## Python API Reference

```python
from spec_ops.security.merkle import (
    ComplianceDeliverable,
    HumanSignoff,
    compile_compliance_manifest,
    verify_compliance_manifest,
    verify_inclusion_proof,
)

# 1. Author deliverable
deliverable = ComplianceDeliverable(
    task_id="TASK-0031",
    prd_id="PRD-0002",
    story_ids=["US-0056", "US-0114"],
    commit_sha="913d0f28b7891234567890abcdef1234567890ab",
    prompt_sha256="aa" * 32,
    test_results_digest="bb" * 32,
    human_signoff=HumanSignoff(
        reviewer="Sasha",
        email="sasha@specops.dev",
        signature="ed25519:sample_sig",
        timestamp="2026-09-29T18:00:00Z",
    ),
)

# 2. Compile manifest
manifest = compile_compliance_manifest([deliverable], standard="soc2")

# 3. Verify manifest
is_valid, errors = verify_compliance_manifest(manifest)
assert is_valid
```

---

## Manifest JSON Schema

Manifests conform to `$schema: https://json-schema.org/draft/2020-12/schema` specifying top-level fields (`version`, `standard`, `generated_at`, `root_hash`, `algorithm`, `serialization`, `tree_size`, `leaves`).
