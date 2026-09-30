# How-To: Visualize Security Posture and Compliance Radar

This guide covers viewing and interpreting the real-time Security Posture and Compliance Radar visualizer dashboard.

---

## Accessing the Security Radar

The Security Radar is built directly into the SpecOps 2D visualizer. To start the local visualizer server:

```bash
spec-ops visualizer
```

Navigate to the **Security** tab or use the deep link:

```text
http://127.0.0.1:8787/#tab=security
```

To export a self-contained, standalone single-file HTML visualizer bundle including the Security Radar:

```bash
spec-ops visualizer export --output dist/project-visualizer.html
```

---

## The Six Security Posture Dimensions

The radar visualizes repository compliance across six security pillars (0 to 100% score for each axis):

1. **Supply-Chain Lockfile Integrity**:
   - Asserts cryptographic hash pinning across `uv.lock` and `pyproject.toml` (governed by ADR-0011).
   - Evaluated locally via `spec-ops security verify-lock`.
2. **Secret & Credential Detection**:
   - Asserts zero uncommitted API keys, tokens, or high-entropy secrets in active worktrees or commits (governed by ADR-0012).
   - Evaluated via `spec-ops health --security`.
3. **Autonomous Worker Sandboxing**:
   - Verifies allowlisted command interceptors and workspace write boundaries (governed by ADR-0010).
4. **Dependency Vulnerability & License Policy**:
   - Scans direct and transitive dependencies against approved OSS license allowlists and zero High/Critical CVEs.
   - Evaluated via `spec-ops audit dependencies`.
5. **Cryptographic Commit Verification & Dual Custody**:
   - Measures the ratio of GPG/SSH signed git commits and dual-custody architect sign-offs on task integrations.
6. **Tamper-Evident Merkle Manifest Integrity**:
   - Verifies SHA-256 Merkle root consistency across specification files, source code, and test receipts.
   - Evaluated via `spec-ops audit verify`.

---

## Continuous CI Verification

To gate pull requests and CI pipelines on security compliance:

```bash
spec-ops health --security
```

Any detected high-entropy secret, lockfile drift, or unauthorized shell command exits with a non-zero code, blocking integration before merge.
