---
id: 0168
title: Automated Conventional Commit RFC-822 Trailer Sanitizer and Signer Pre-Gate
status: Complete
dependencies:
- TASK-0048
- TASK-0163
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0014
- ADR-0016
governing_prds:
- PRD-0002
governing_stories:
- US-0113
target_bc: security
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-02T01:21:23.930762+00:00'
commit_signature_status: SIGNED
has_signed_commits: true
---

# TASK-0168: Automated Conventional Commit RFC-822 Trailer Sanitizer and Signer Pre-Gate

## Summary
Implement an automated commit trailer sanitizer and cryptographic signature pre-gate validator (`src/spec_ops/security/trailer_sanitizer.py`). Governed by ADR-0001 and ADR-0016, this engine verifies that all git commit messages on task branches conform to Conventional Commits standards and contain valid RFC-822 trailers (`SpecOps-Task`, `SpecOps-Story`, `SpecOps-PRD`, `SpecOps-ADR`) before integration (`spec-ops security check-trailers`).

## Problem Statement & Context
Autonomous agent swarms and human developers can inadvertently create messy, unstructured commit messages or omit critical traceability trailers. Incomplete trailers break the bidirectional relational graph and compromise compliance auditability. An automated trailer sanitizer validates commit metadata format and verifies trailers against registered tasks before worktrees merge.

## Key Requirements & Scope
1. **Commit Trailer Sanitizer Engine (`src/spec_ops/security/trailer_sanitizer.py`)**:
   - Parses git commit messages across specified commit ranges (e.g. `main..HEAD`).
   - Validates Conventional Commit header format (`type(scope): subject`).
   - Extracts and validates RFC-822 structured trailers (`SpecOps-Task: TASK-XXXX`, etc.).
   - Cross-checks referenced Task, Story, PRD, and ADR IDs against project registry files.
2. **Commit Trailer CLI (`spec-ops security check-trailers [--range <rev-range>] [--strict] [--json]`)**:
   - Analyzes commit messages in the specified revision range.
   - Exits with code 0 if all commits comply, or code 1 with actionable formatting feedback if invalid.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Module in `src/spec_ops/security/trailer_sanitizer.py` must stay strictly under 400 lines (ADR-0002).
- **Bidirectional Traceability (ADR-0001)**: Every commit must cite its governing task ID.
- **Mutation Testing Scope**: Target module `src/spec_ops/security/trailer_sanitizer.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Validating compliant commits with full trailers
```gherkin
Given a git branch with conventional commit messages and valid SpecOps trailers
When the trailer sanitizer validates the commit range
Then all commits pass validation
And the command terminates with exit code 0
```

### Scenario 2: Rejecting commits missing required task trailers
```gherkin
Given a git commit lacking the required "SpecOps-Task" trailer
When the trailer sanitizer runs with strict mode
Then the non-compliant commit is flagged with missing trailer details
And the command terminates with exit code 1
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that any well-formed RFC-822 trailer block is parsed into identical key-value dictionary mappings without value truncation or key loss.
