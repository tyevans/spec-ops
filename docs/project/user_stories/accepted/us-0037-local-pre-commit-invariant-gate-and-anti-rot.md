---
id: '0037'
title: Local Pre-Commit Invariant Gate and Proactive Anti-Rot Warnings
status: Accepted
created: 2026-09-29
persona: Riley (The Human IC Developer)
feature: FEAT-GTE-01
governing_prd: PRD-0004
---

# US-0037 — Local Pre-Commit Invariant Gate and Proactive Anti-Rot Warnings

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As an** human software engineer writing code in my local IDE,  
**I want** local pre-commit hooks to enforce file length invariants (<500 lines) and provide proactive refactoring alerts (>=400 lines) before I commit,  
**So that** I receive immediate local feedback on modularity and PMaC compliance, avoiding frustrating CI round-trip failures.

## Acceptance Criteria

```gherkin
Scenario: Blocking staged file that exceeds hard invariant limit
Given a staged source file "src/spec_ops/core/parser.py" with 512 lines
When the engineer executes "git commit -m 'feat: parser extension'"
Then the "spec-ops-health" pre-commit hook aborts the commit
And the terminal displays "File Length Violation: src/spec_ops/core/parser.py (512 lines > 500 line limit)"
And the commit is rejected until the file is decomposed into modular submodules.
```

```gherkin
Scenario: Proactive warning on files approaching limit without blocking commit
Given a staged source file "src/spec_ops/visualizer/generator.py" with 420 lines
And no source files exceed the hard 500-line invariant limit
When the engineer executes "git commit -m 'feat: visualizer updates'"
Then the "spec-ops-health" pre-commit hook allows the commit to proceed
And the terminal displays a warning: "⚠️ Proactive Refactoring Warning: src/spec_ops/visualizer/generator.py (420 lines >= 400 line warning threshold)".
```

```gherkin
Scenario: Verifying PRIORITY.md and disk state synchronization
Given "docs/project/backlog/PRIORITY.md" is synchronized with tasks on disk
When the pre-commit hook runs "spec-ops health"
Then the check passes with "PRIORITY.md is synchronized with disk state.".
```

## Rationale & Compelling Value
Integrates directly into existing developer habits (`git commit`). Proactive alerts at 400 lines prevent files from ever crossing the catastrophic 500-line threshold.
