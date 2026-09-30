---
id: '0006'
title: PRD Vertical Slice Decomposition Engine
status: Complete
created: 2026-09-29
dependencies:
- TASK-0001
- TASK-0004
governing_adrs:
- ADR-0001
- ADR-0006
governing_prds:
- PRD-0001
governing_stories:
- US-0003
target_bc: prd
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-09-30T18:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---


# TASK-0006: PRD Vertical Slice Decomposition Engine

## Summary
Implement `spec-ops prd decompose` breaking complex PRD documents into thin vertical slices, user story files, and architectural spike tasks with governing ADR links.

## Definition of Done
1. `PRDDecomposer` inspects checkable outcomes and stories in PRD documents.
2. Generates corresponding task markdown files into `backlog/proposed/`.
3. Optionally generates an architectural spike task for unverified technical invariants.
4. Updates PRD frontmatter with generated task references.
