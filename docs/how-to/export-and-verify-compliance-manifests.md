# How-To: Export and Verify Tamper-Evident Merkle Compliance Manifests

This guide explains how to export deterministic cryptographic compliance manifests and mathematically verify end-to-end SDLC traceability using SpecOps audit commands governed by [ADR-0016](../project/adrs/accepted/adr-0016-tamper-evident-merkle-compliance-manifests.md).

---

## Compiling and Exporting Compliance Audit Manifests

To compile all completed deliverables in your project into an immutable, Merkle-hashed compliance package:

```bash
spec-ops audit export --standard soc2 --output dist/compliance/
```

SpecOps gathers all deliverables from `docs/project/backlog/complete/`, extracting:
- Governing PRD ID and linked User Story Gherkin acceptance criteria
- Completed task frontmatter and metadata
- Agent prompt SHA-256 digest
- Test execution logs digest
- Authorized human reviewer sign-off attestation
- Git commit SHA

The command deterministically constructs an RFC 6962 power-of-2 binary Merkle tree serialized via RFC 8785 JSON Canonicalization Scheme (JCS) and writes:
1. `dist/compliance/soc2-audit-manifest.json`: The complete audit manifest with all deliverables and leaf hashes.
2. `dist/compliance/MERKLE_ROOT`: The top-level SHA-256 root digest.

Example output:
```text
✨ Compiled compliance audit manifest: dist/compliance/soc2-audit-manifest.json
✨ Generated top-level Merkle root: dist/compliance/MERKLE_ROOT
   Standard:     SOC2
   Deliverables: 45
   Merkle Root:  e742deb33b67ff25ef3156da19835204a1ce9e8036889c9db79aa41b40417cf1
```

---

## Verifying Compliance Manifests and Detecting Tampering

To verify the integrity of an exported audit manifest and cross-check it against repository disk state and git history:

```bash
spec-ops audit verify --manifest dist/compliance/soc2-audit-manifest.json
```

The verification engine performs a multi-stage validation:
1. **Internal Merkle Tree Verification**: Recomputes all leaf hashes (`0x00` domain prefix) and interior node hashes (`0x01` domain prefix) to guarantee the manifest has not been altered.
2. **Companion Root Digest Check**: Confirms the companion `MERKLE_ROOT` matches the manifest root hash.
3. **Repository Disk Traceability**: Confirms each completed deliverable task exists in `docs/project/backlog/complete/` and verifies that prompt digests, commit SHAs, and sign-offs match repository disk state.

When all checks pass, the command exits with returncode 0:
```text
✅ Compliance Audit Verification PASSED:
   Manifest:     dist/compliance/soc2-audit-manifest.json
   Deliverables: 45
   Merkle Root:  e742deb33b67ff25ef3156da19835204a1ce9e8036889c9db79aa41b40417cf1
```

If an unauthorized or out-of-band modification has occurred (such as editing a completed task file or altering a sign-off signature), verification fails with returncode 1 and reports the corrupted task ID alongside the expected and computed SHA-256 integrity digests:

```text
❌ Compliance Verification Failed: Deliverable integrity violation detected.
   Corrupted Task ID: TASK-0030
   Expected SHA-256:  37c71216df4e149063c4700002c8e02591e89398...
   Computed SHA-256:  9b12a3e7569eff106cab2326994e38a166a6c456...
   - Out-of-band audit trail tampering detected in task 'TASK-0030': disk state diverged from manifest.
```
