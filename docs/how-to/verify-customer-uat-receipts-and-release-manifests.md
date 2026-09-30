# How-To: Verify Living Customer UAT Receipts and Release Manifests

This guide demonstrates how to validate customer UAT sign-offs (`docs/project/product/uat-signoff.json`), generate cryptographic release manifests (`dist/releases/PRD-XXXX-release-manifest.json`), and perform headless preflight verification.

---

## 1. Schema for Customer UAT Sign-Offs

Customer UAT sign-offs are version-locked in git at `docs/project/product/uat-signoff.json`. The schema binds passing automated Gherkin test outcomes to formal human PM approvals:

```json
{
  "$schema": "spec-ops/uat-signoff-v1",
  "version": "1.0",
  "signoffs": {
    "PRD-0003:1": {
      "outcome_id": "1",
      "prd_id": "PRD-0003",
      "status": "Approved",
      "reviewer": "Taylor <taylor@example.com>",
      "timestamp": "2026-09-29T18:00:00Z",
      "notes": "Verified local studio web server responsiveness on Chromium",
      "test_correlation": {
        "scenario": "Scenario: Inspecting Customer UAT Readiness Matrix",
        "story_id": "US-0046",
        "passed": true,
        "test_run_id": "ci-run-8492"
      },
      "history": [
        {
          "timestamp": "2026-09-29T17:30:00Z",
          "reviewer": "Taylor <taylor@example.com>",
          "status": "Pending",
          "notes": "Awaiting CI test run completion"
        }
      ]
    }
  }
}
```

---

## 2. Reconciling Concurrent PM Sign-Offs

When multiple product managers sign off concurrently across branches, `reconcile_signoffs` performs deterministic Last-Write-Wins merging while preserving audit history:

```python
from spec_ops.prd.uat_receipt import reconcile_signoffs, serialize_canonical_json

merged_state = reconcile_signoffs(local_signoffs, remote_signoffs)
serialized_json = serialize_canonical_json(merged_state)
```

Properties guaranteed:
- **Chronological Idempotency**: Merging identical states produces no mutations.
- **Deterministic Ordering**: Top-level keys are sorted alphabetically, eliminating spurious git merge conflicts.
- **Audit Preservation**: Historical reviews are preserved chronologically.

---

## 3. Generating a Cryptographic Release Manifest

Upon shipping a PRD, generate a tamper-evident release reconciliation manifest:

```python
from spec_ops.prd.manifest import generate_release_manifest

manifest = generate_release_manifest(
    repo_root=".",
    prd_id="PRD-0003",
    prd_title="Product Discovery & Living UAT Verification",
    target_persona="Taylor",
    completed_tasks=[{"id": "TASK-0040", "commit_sha": "abc1234"}],
    test_summary={"status": "Passed (CI)", "total_scenarios": 58, "failed_scenarios": 0},
    uat_summary={"status": "Approved", "total_outcomes": 5, "approved_outcomes": 5},
    output_path="dist/releases/PRD-0003-release-manifest.json",
)
```

The manifest cryptographically binds the git tree SHA-256 digest, completed task commits, test run results, and UAT sign-offs with zero external crypto dependencies (built on standard library `hashlib.sha256`).

---

## 4. Headless Verification in CI

CI preflight gates verify release manifests in <50ms without network access or heavy tooling:

```python
from spec_ops.prd.manifest import verify_release_manifest

valid, violations = verify_release_manifest("dist/releases/PRD-0003-release-manifest.json", repo_root=".")
if not valid:
    for violation in violations:
        print(f"❌ {violation}")
    raise SystemExit(1)
```

Verification automatically fails if:
1. Working tree contains uncommitted diffs or untracked changes.
2. Any git-tracked file differs from the verified tree digest (tampering detection).
3. Manifest cryptographic signature fails verification.
4. Any Gherkin test failed or mandatory PM UAT sign-off is missing.
