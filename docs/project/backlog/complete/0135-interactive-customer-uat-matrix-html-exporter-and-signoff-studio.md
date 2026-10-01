---
id: '0135'
title: Interactive Customer UAT Matrix HTML Exporter and Signoff Studio
status: Complete
dependencies:
- TASK-0126
- TASK-0131
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0006
- ADR-0007
- ADR-0013
- ADR-0014
governing_prds:
- PRD-0001
- PRD-0003
governing_stories:
- US-0046
- US-0094
target_bc: prd
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T11:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0135: Interactive Customer UAT Matrix HTML Exporter and Signoff Studio

## Summary
Implement the interactive Customer UAT Matrix HTML exporter (`spec-ops prd uat export --prd <ID> [--format html]`) and visual sign-off studio interface. Fulfilling PRD-0003 Checkable Outcome 5 and ADR-0014, this engine generates a tamper-evident, self-contained HTML acceptance report displaying real-time BDD scenario execution proofs, cryptographic customer signatures, and automated release readiness badges.

## Problem Statement & Context
Non-technical product managers, QA leads, and customer stakeholders cannot easily review terminal test outputs or raw JSON receipts. They require a zero-dependency, portable visual document that presents checkable PRD outcomes, mapped BDD scenarios, pass/fail proof status, and verified cryptographic signatures (`ed25519` UAT receipts) for formal customer acceptance sign-offs.

## Key Requirements & Scope
1. **Portable HTML UAT Matrix Exporter (`spec-ops prd uat export`)**:
   - Compiles a standalone HTML acceptance matrix with embedded CSS/SVG (zero external CDN or network dependencies).
   - Renders checkable outcomes from `docs/project/product/accepted/PRD-XXXX.md`.
   - Links each outcome to corresponding Gherkin BDD scenario execution logs and pass/fail states.
   - Embeds cryptographic signature verification status and timestamp from `docs/project/product/uat-signoff.json` (ADR-0014).
2. **Visual UAT Sign-Off Studio**:
   - Integrates into `spec-ops prd studio` to allow interactive review and one-click cryptographic receipt generation.
   - Exports downloadable PDF/HTML customer acceptance certificates.
3. **Blackbox Frontdoor & Diataxis Synchronization**:
   - 100% test pass rate verifying observable HTML/CLI output contracts.
   - Synchronize `docs/reference/cli.md` and `DEFAULT_REFERENCE_CLI`.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: New UAT HTML export module in `src/spec_ops/prd/uat_export.py` must stay strictly under 400 lines (ADR-0002).
- **Cryptographic Receipt Integrity (ADR-0014)**: Exported HTML documents preserve and verify Ed25519 signature digests without external dependencies.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/prd/uat_export.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Standalone HTML Customer UAT Acceptance Matrix
```gherkin
Given an accepted PRD "PRD-0003" with checkable outcomes and approved customer signatures
When the engineer runs "spec-ops prd uat export --prd PRD-0003 --format html"
Then a standalone HTML matrix is generated
And the HTML contains verified checkable outcomes and cryptographic verification badges
```

### Scenario 2: Tamper-Evident Digest in Exported Acceptance Matrix
```gherkin
Given a generated HTML UAT acceptance matrix for "PRD-0003"
When the file contents are validated
Then the embedded cryptographic verification proof matches the signed ledger
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary set of checkable outcomes and signoff records, HTML serialization produces valid, well-formed HTML without unescaped script injections.
