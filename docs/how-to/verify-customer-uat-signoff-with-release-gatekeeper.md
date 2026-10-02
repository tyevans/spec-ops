# How-To: Verify Customer UAT Sign-Off with the Release Gatekeeper

This guide demonstrates how to evaluate customer UAT readiness, export tamper-evident cryptographic sign-off tokens, and enforce automated release gatekeeping prior to deployment.

---

## Evaluating Release Readiness

To evaluate whether a PRD has achieved complete customer acceptance and signed-off outcomes:

```bash
spec-ops prd gate --prd PRD-0003
```

When all checkable outcomes possess approved sign-offs:

```text
=== Customer UAT Release Gate: PRD-0003 ===
Gate Decision: ✅ PASS
Readiness: 100.0% (3/3 outcomes approved)
Token Signature: 4f9b8c12a7d6e42b... (Valid)
```

The command terminates with exit code `0`.

---

## Enforcing Strict Release Gates

To block deployment pipelines when any unverified outcomes or signature anomalies are detected:

```bash
spec-ops prd gate --prd PRD-0003 --strict
```

If any checkable criteria lack approved sign-offs:

```text
=== Customer UAT Release Gate: PRD-0003 ===
Gate Decision: ❌ BLOCKED
Readiness: 66.7% (2/3 outcomes approved)

Blocking Release Criteria:
  - Outcome 3: Customer sign-off is 'Pending' (Approved required)
```

The command terminates with exit code `1`, halting automated release workflows.

---

## Generating Machine-Readable JSON Reports

To integrate with CI/CD deployment jobs, request structured JSON output:

```bash
spec-ops prd gate --prd PRD-0003 --json
```

Output:

```json
{
  "approved_outcomes": 3,
  "blocking_reasons": [],
  "decision": "PASS",
  "outcomes": [
    {
      "blockers": [],
      "notes": "",
      "outcome_id": "1",
      "outcome_text": "Live customer visualizer displays all checkable outcomes",
      "reviewer": "Taylor (Lead PM) <taylor@specops.local>",
      "status": "Approved",
      "timestamp": "2026-10-01T12:00:00+00:00",
      "token_verified": true,
      "verified": true
    }
  ],
  "prd_id": "PRD-0003",
  "readiness_percentage": 100.0,
  "token_path": ".specops/uat_receipts/PRD-0003-uat-token.json",
  "token_signature": "4f9b8c12a7d6e42b318d96204c35e83917457492c1ad9092eb22442435d6428e",
  "total_outcomes": 3,
  "verified_outcomes": 3
}
```

---

## Exporting Cryptographic UAT Sign-Off Tokens

To seal verified outcomes into a tamper-evident cryptographic token under `.specops/uat_receipts/`:

```bash
spec-ops prd gate --prd PRD-0003 --export
```

This generates `.specops/uat_receipts/PRD-0003-uat-token.json` sealed with the current git tree digest and deterministic SHA-256 signature.
