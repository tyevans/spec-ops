# How-To: Audit Dependencies and Manage Security Policy Waivers

This guide explains how to audit dependencies for High and Critical CVE vulnerabilities, enforce open-source software license allowlists, and author cryptographically signed policy waivers for audited exceptions.

---

## Auditing Dependencies for Vulnerabilities and Incompatible Licenses

To scan direct and transitive dependencies against public vulnerability databases (OSV) and enforce license allowlists:

```bash
spec-ops audit dependencies
```

The scanner inspects dependencies in `uv.lock` or `pyproject.toml`:
- Queries OSV for High and Critical CVE advisories.
- Verifies package licenses against the approved allowlist in `specops.toml`.
- Evaluates valid, unexpired policy waivers under `docs/project/compliance/waivers/`.

When all packages pass or have valid waivers, the command exits with code 0:

```text
✅ Dependency audit passed: all dependencies satisfy vulnerability and license policies.
```

If un-waived High/Critical CVEs or license violations are found, the command exits with code 1 and outputs detailed diagnostic information.

---

## Configuring Open-Source License Policies

In `specops.toml`, configure the allowlist of permitted open-source licenses:

```toml
[security.licenses]
allowed = ["MIT", "Apache-2.0", "BSD-3-Clause", "ISC"]
profile = "permissive"
```

Packages introducing viral copyleft or incompatible licenses (e.g., AGPL-3.0 or GPL-3.0) will be flagged and blocked from transitioning tasks to `refined/` or `complete/`.

---

## Authoring and Signing Policy Waivers

When an exception is reviewed and approved by trust and security officers, store a signed waiver in `docs/project/compliance/waivers/WAIVER-*.md`:

```yaml
---
id: WAIVER-001
package: audited-package
license: AGPL-3.0
signer: Sasha
expires: 2028-12-31
signature: sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef
status: Approved
reason: Approved for internal CLI analysis tool only; isolated from SaaS backend
---

# Policy Waiver: WAIVER-001

Audited by Sasha. This package is restricted to developer tooling and excluded from distribution artifacts.
```

Waivers are validated cryptographically and checked for expiration. Once expired, the scanner automatically rejects the waived package until renewed.

---

## Running in Air-Gapped and Offline Environments

For hermetic CI pipelines or air-gapped environments without external internet egress, run the scanner in offline mode:

```bash
spec-ops audit dependencies --offline
```

The scanner will evaluate against local vulnerability caches stored in `.spec-ops/cve_cache.json` or `docs/project/compliance/cve_cache.json`.
