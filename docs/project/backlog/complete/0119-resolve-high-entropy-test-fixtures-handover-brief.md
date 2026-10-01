---
id: 0119
title: Resolve High-Entropy Test Fixtures Triggering Security Scanner in Handover
  Brief Tests
status: Complete
dependencies:
- TASK-0097
governing_adrs:
- ADR-0001
- ADR-0003
- ADR-0009
- ADR-0010
governing_prds:
- PRD-0004
governing_stories:
- US-0090
target_bc: rescue
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T00:22:47.024255+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0119: Resolve High-Entropy Test Fixtures Triggering Security Scanner in Handover Brief Tests

## Summary
Refactor test fixture secret strings in test suites (e.g. `tests/test_handover_unit.py` and `tests/test_handover_properties.py`) so they do not trigger the preflight security secret scanner (`spec-ops health --security`) via static regex matching.

## Problem Statement & Context
During `spec-ops rescue TASK-0097 --complete`, `spec-ops health --security` failed due to detection of dummy credential fixtures in:
- `tests/test_handover_properties.py` (Cryptographic Private Key)
- `tests/test_handover_unit.py` (OpenAI/Anthropic API Key, AWS Access Key ID, AWS Secret Access Key, GitHub Access Token, Slack Token, Cryptographic Private Key, High-Entropy Credential Assignment)

These dummy tokens were authored as literal strings to test redaction/sanitization in worktree handover briefs. Because the preflight secret scanner statically analyzes source code files for credential patterns, these literal dummy tokens triggered false positives, blocking task integration.

In accordance with the SpecOps SDLC Orchestration Failure Protocol (dogfooding invariant), this defect was tracked to ensure tests dynamically assemble mock tokens at runtime (e.g. via string concatenation or generation) without embedding static credential signatures in the codebase.

## User Stories & Scenarios Satisfied
- **US-0090: Preserved Worktree Handover Brief and Human Remediation Cheatsheet**
  - *Scenario: Secret Redaction in Handover Brief without Preflight False Positives*
    - Given a worktree environment containing dummy secrets for testing redaction
    - When tests verify that sensitive credentials are scrubbed from handover briefs
    - Then test fixtures are constructed dynamically at runtime
    - And `spec-ops health --security` passes cleanly with zero false positive detections.

## Architectural Invariants & Seams
- **Security & Supply-Chain Hard Invariants (ADR-0010, ADR-0011)**: Zero unredacted secrets or scanner alerts in the repository.
- **Blackbox Frontdoor Verification (ADR-0003)**: Handover generator sanitize/redaction capabilities remain fully verified via public interfaces.
- **Property-Based Testing (ADR-0009)**: Generative property tests verify token redaction across randomized inputs.

## Definition of Done (Blackbox Frontdoor TDD)
1. All static secret regex matches in test fixtures replaced with dynamic runtime construction (string concatenation/formatting).
2. `spec-ops health --security` runs with zero secret leak findings.
3. Handover unit and property tests pass 100% with full redaction verification intact.
