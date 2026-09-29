---
id: '0005'
title: Codebase Health Checker and File Invariant Verifier
status: Complete
created: 2026-09-29
dependencies:
  - TASK-0001
governing_adrs:
  - ADR-0002
governing_prds:
  - PRD-0001
governing_stories:
  - US-0002
target_bc: backlog
---

# TASK-0005: Codebase Health Checker and File Invariant Verifier

## Summary
Implement `spec-ops health` checking the non-negotiable <500 lines file length limit across all source code, backlog buffer thresholds, and PRIORITY.md disk synchronization.

## Definition of Done
1. Recursive source file scanner detects any file exceeding configured line limit (<500).
2. PRIORITY.md synchronization validator detects stale or broken task directory references.
3. Health check reports buffer status (`OPTIMAL`, `UNDER_BUFFERED`, `OVER_BUFFERED`).
4. Non-zero exit code emitted on violations to guard CI preflights.
