# How-To: Verify Cryptographic Commit Attestation and Keyrings

This guide explains how to audit git commit signatures, enforce public key keyring verification, and detect unsigned or forged commits using `spec-ops security verify-commits` governed by [ADR-0014](../project/adrs/accepted/adr-0014-cryptographic-release-manifests-and-tamper-evident-artifact-verification.md) and [ADR-0016](../project/adrs/accepted/adr-0016-dual-custody-human-review-gate-and-cryptographic-commit-signing.md).

---

## Overview

In autonomous agent and hybrid human-agent engineering workflows, untracked or spoofed git commits present significant supply-chain risks. SpecOps mandates that all task commits be cryptographically signed (`commit.gpgsign = true`).

The `spec-ops security verify-commits` engine:
- Extracts and parses raw git commit objects and embedded signature blocks (`gpgsig`)
- Validates SSH Ed25519, GPG, and Sigstore cosign signatures
- Cross-references commit authors, committers, and signer identities against authorized maintainer keyrings (e.g. `.allowed_signers`)
- Enforces unbroken cryptographic provenance across branch ranges

---

## Verifying Commit Signatures in a Revision Range

To verify that the most recent commit or pull request range carries authentic signatures:

```bash
uv run spec-ops security verify-commits --range HEAD~1..HEAD
```

Example successful audit:
```text
=== SpecOps Cryptographic Commit Attestation Audit ===
Revision Range: HEAD~1..HEAD
Keyring:        Default System / Git Keyring
Evaluated:      1 commit(s)
Verified:       1 valid
Unverified:     0 invalid/unsigned

✅ Cryptographic Provenance Verified: All commits contain valid signatures.
```

---

## Verifying Against an Explicit Keyring

To evaluate signatures against a specific SSH `allowed_signers` file or authorized team keyring:

```bash
uv run spec-ops security verify-commits --range main..HEAD --keyring .allowed_signers
```

If an unauthorized or unrecognized key was used to sign a commit, the audit flags the violation:
```text
=== SpecOps Cryptographic Commit Attestation Audit ===
Revision Range: main..HEAD
Keyring:        .allowed_signers
Evaluated:      3 commit(s)
Verified:       2 valid
Unverified:     1 invalid/unsigned

❌ Attestation Violations Detected:
  ⚠️  Commit a1b2c3d4 [UNTRUSTED_SIGNER] by Unknown <unknown@attacker.io>
     - Signer 'unknown@attacker.io' (key: SHA256:xyz) is not in authorized keyring.
```

---

## Enforcing Strict CI Verification Gates

When integrating branches into protected release streams, run in `--strict` mode. The command exits with status code `1` if any commit lacks a valid signature:

```bash
uv run spec-ops security verify-commits --range origin/main..HEAD --strict
```

---

## Exporting Machine-Readable Verification JSON

To pipe attestation results to CI security dashboards or SOC2 compliance pipelines, add `--json`:

```bash
uv run spec-ops security verify-commits --range origin/main..HEAD --json
```

---

## Verifying Documentation and Drift

To confirm documentation references and CLI arguments stay synchronized:

```bash
uv run spec-ops docs audit
uv run spec-ops docs build
```
