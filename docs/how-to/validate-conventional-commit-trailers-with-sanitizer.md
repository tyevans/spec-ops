# How-To: Validate Conventional Commit Trailers with Sanitizer Pre-Gate

This guide explains how to verify that git commit messages conform to Conventional Commits standards and contain valid RFC-822 SpecOps traceability trailers using `spec-ops security check-trailers`, governed by [ADR-0001](../project/adrs/accepted/adr-0001-specification-as-code-pmac.md) and [ADR-0016](../project/adrs/accepted/adr-0016-dual-custody-cryptographic-commit-signing-and-human-review-gate.md).

---

## Overview

In multi-agent collaborative workflows, autonomous worker agents and human engineers commit code to task branches. To maintain complete bidirectional traceability across Personas -> PRDs -> Stories -> Tasks -> Commits, every commit must follow Conventional Commits formatting and include structured RFC-822 trailers.

The Trailer Sanitizer pre-gate validates:
- Conventional Commit subject syntax: `type(scope): subject` (e.g. `feat(security): add trailer check`)
- Presence of the required `SpecOps-Task: TASK-XXXX` trailer
- Optional traceability trailers: `SpecOps-Story`, `SpecOps-PRD`, `SpecOps-ADR`
- Integrity cross-checks verifying that referenced task, story, PRD, and ADR IDs exist in `docs/project/`

---

## Validating Commits in a Revision Range

To validate all commits on the current branch against `main`:

```bash
uv run spec-ops security check-trailers --range main..HEAD
```

Output:
```text
=== Conventional Commit & RFC-822 Trailer Verification (main..HEAD) ===
Total Commits: 1
Compliant:     1/1

✅ Commit c649a6b3: feat(task-0167): Interactive Terminal Dashboard Multi-Tab Live Monitor
   Trailers: SpecOps-Task=TASK-0167, SpecOps-Story=US-0115, US-0117, SpecOps-PRD=PRD-0001, PRD-0006

✨ All commits comply with Conventional Commits and RFC-822 trailer standards.
```

---

## Enforcing Strict Traceability Validation

In strict mode, any missing trailer or unresolved entity reference causes the validator to exit with code `1`:

```bash
uv run spec-ops security check-trailers --range main..HEAD --strict
```

If a commit lacks the required `SpecOps-Task` trailer:

```text
=== Conventional Commit & RFC-822 Trailer Verification (main..HEAD) ===
Total Commits: 1
Compliant:     0/1

❌ Commit e8f91b02: feat(core): missing task trailer
   Missing:  SpecOps-Task
   Error:    Missing required trailer 'SpecOps-Task'.

❌ Commit trailer verification failed. Correct formatting or supply required trailers.
```

---

## Emitting Machine-Readable Validation Reports

To integrate with CI preflight gates and output JSON:

```bash
uv run spec-ops security check-trailers --range main..HEAD --json
```

Output:
```json
[
  {
    "commit_hash": "c649a6b3",
    "subject": "feat(task-0167): Interactive Terminal Dashboard Multi-Tab Live Monitor",
    "is_valid": true,
    "conventional_valid": true,
    "trailers": {
      "SpecOps-Task": "TASK-0167",
      "SpecOps-Story": "US-0115, US-0117"
    },
    "missing_trailers": [],
    "unresolved_references": [],
    "errors": [],
    "warnings": []
  }
]
```
