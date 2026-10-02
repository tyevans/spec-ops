---
id: '0251'
title: Automated Security & Auditing Scaffolding and Commit Provenance Baselining
  in Adoption
status: Refined
governing_adrs:
- ADR-0001
- ADR-0010
- ADR-0011
- ADR-0012
governing_prds:
- PRD-0007
governing_stories:
- US-0128
target_bc: security
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T19:52:11.690133+00:00'
persona: Devon
---

# TASK-0251: Automated Security & Auditing Scaffolding and Commit Provenance Baselining in Adoption

## Summary
Extend `spec-ops adopt` to automatically install the pre-commit security hook, record the adoption HEAD commit as the provenance audit baseline in `specops.toml`, and update `spec-ops audit provenance` to support `--since <ref>` and baseline commit filtering so historical pre-adoption commits are grandfathered without triggering compliance failures.

## Problem Statement & Context
Brownfield repositories onboarding into SpecOps currently require manual execution of security hooks and configuration. When compliance teams run `spec-ops audit provenance`, the audit inspects the entire git history, flagging hundreds of grandfathered legacy commits that predate SpecOps as unanchored or missing trailers. An adoption baseline commit and rev-range filtering (`--since`) are required to achieve 100% provenance compliance forward-looking.

## Proposed Solution & Remediation Plan
1. In `src/spec_ops/cli/adopt_handler.py`:
   - Inspect HEAD git commit and record it as `[audit.provenance] baseline_commit` in `specops.toml`.
   - Automatically install `.git/hooks/pre-commit` to enforce security sentinels and secret scans on staged changes.
   - Configure `[security]` with configurable entropy thresholds in `specops.toml`.
2. In `src/spec_ops/cli/parser_audit.py`:
   - Add `--since` argument to `spec-ops audit provenance` to accept revision ranges, commit hashes, or branch references.
3. In `src/spec_ops/core/provenance.py`:
   - Accept `since: str | None = None` and `baseline_commit: str | None = None`.
   - When extracting commit records, filter out commits preceding the baseline commit or outside the specified revision range.
   - Mark grandfathered historical commits as legacy without lowering the forward-looking integrity score.
4. Author blackbox frontdoor BDD tests verifying rev-range provenance auditing and automated security hook installation.

## Definition of Done (Blackbox Frontdoor TDD)
1. `spec-ops adopt` installs `.git/hooks/pre-commit` and records `baseline_commit` in `specops.toml`.
2. `spec-ops audit provenance --since <ref>` audits commits only within the specified range.
3. Repositories with pre-existing unanchored history achieve 100% provenance integrity when evaluated against the baseline commit.
4. 100% blackbox frontdoor test pass rate with 0 private backdoor mocks (ADR-0003).
5. Code strictly adheres to ADR-0002 (<500 lines limit).
