---
id: '0250'
title: Brownfield Technical Debt Baselining Ratchet and AST Decomposition Task Emission
status: Complete
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0009
governing_prds:
- PRD-0007
governing_stories:
- US-0126
target_bc: core
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T19:52:11.020920+00:00'
commit_signature_status: SIGNED
persona: Devon
has_signed_commits: true
---

# TASK-0250: Brownfield Technical Debt Baselining Ratchet and AST Decomposition Task Emission

## Summary
Harden the technical debt baselining engine to enforce an architectural ratchet: grandfathered legacy files recorded during `spec-ops adopt --grandfather-debt` cannot expand beyond their baselined line count, while newly created files strictly adhere to the <500 lines limit. Ensure emitted refactor tasks contain valid AST decomposition blueprints.

## Problem Statement & Context
When brownfield projects onboard into SpecOps, legacy oversized files are recorded in `.spec-ops/debt_baseline.json`. However, without a strict ratchet check, developers or agents might continue adding code to already oversized files, worsening tech debt. The health check must verify that grandfathered files have not grown, and the adoption engine must emit valid, actionable AST decomposition tasks into `docs/project/backlog/proposed/`.

## Proposed Solution & Remediation Plan
1. In `src/spec_ops/core/debt_baseline.py`, record file line counts at the time of adoption alongside relative paths.
2. In `src/spec_ops/core/health.py`, compare current line counts of grandfathered files against their baselined counts:
   - If current <= baseline, the grandfathered file is exempted.
   - If current > baseline, flag an unapproved debt regression violation.
   - Any non-grandfathered file exceeding the file length limit is flagged as a violation.
3. Verify that `spec-ops adopt` emits valid PMaC refactor tasks with AST decomposition suggestions into `docs/project/backlog/proposed/`.
4. Author blackbox frontdoor tests verifying the debt ratchet and task generation.

## Definition of Done (Blackbox Frontdoor TDD)
1. `spec-ops adopt --grandfather-debt` baselines existing oversized files with exact line counts.
2. `spec-ops health` passes for baselined files if line counts do not increase.
3. `spec-ops health` fails with a clear violation if a baselined file expands beyond its recorded count.
4. Newly added files exceeding 500 lines are strictly rejected.
5. 100% blackbox frontdoor test pass rate with 0 private backdoor mocks (ADR-0003).
6. Code strictly adheres to ADR-0002 (<500 lines limit).
