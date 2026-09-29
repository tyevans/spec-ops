---
id: '0088'
title: Selective Patch Takeover and Partial File Salvage from Stalled Worktrees
status: Accepted
created: 2026-09-29
persona: Riley (The Human IC Developer)
feature: FEAT-RESC-02
governing_prd: PRD-0004
---

# US-0088 — Selective Patch Takeover and Partial File Salvage from Stalled Worktrees

## Governing PRD
- [`PRD-0004: Autonomous Multi-Worker Fleet & Preserved Worktree Rescue Engine`](../../product/accepted/prd-0004-autonomous-multi-worker-fleet-and-worktree-rescue-engine.md)

## User Story

**As a** human software engineer taking over an incomplete or partially broken worktree,
  - **I want** to run `spec-ops rescue patch <task-id>` to selectively stage viable source modules and tests while discarding hallucinated files or bloated code,
  - **So that** I can salvage high-value agent-generated logic without inheriting dirty worktree baggage, failing tests, or architectural violations.

## Acceptance Criteria

```gherkin
Scenario: Selectively cherry-picking valid domain files while discarding hallucinated scrap
Given a stalled worktree ".worktrees/task-0018" with modified files:
| File                                | Description                                |
| src/spec_ops/core/models.py         | Valid pure domain models added by agent    |
| tests/core/test_models.py           | Valid BDD acceptance tests added by agent  |
| src/spec_ops/scratch_debug.py       | Untracked hallucinated scratch file        |
| src/spec_ops/core/parser.py         | 600-line bloated attempt breaking limits   |
When the engineer executes "spec-ops rescue patch TASK-0018 --include 'src/spec_ops/core/models.py' --include 'tests/core/test_models.py'"
Then only the specified files are staged into the rescue changeset
And untracked scratch files and the bloated "parser.py" remain uncommitted and excluded from preflight.
```
```gherkin
Scenario: Preflight verification of the selectively salvaged patch
Given the engineer has selectively staged the valid models and tests for "TASK-0018"
And implemented the missing parser logic cleanly in "src/spec_ops/core/parser.py" (<400 lines)
When the engineer executes "spec-ops rescue TASK-0018 --complete --salvage"
Then preflight verification runs exclusively on the curated staging area
And passes with 0 file limit violations and 100% test pass rate.
```
```gherkin
Scenario: Squash-merging salvaged patch into main with dual-custody provenance trailers
Given preflight verification succeeds on the salvaged patch for "TASK-0018"
When the rescue manager merges the branch into "main" under MERGE_LOCK
Then the squash commit message includes structured dual-custody trailers:
"""
feat(task-0018): Implement Core Domain Models (rescued)
SpecOps-Task: TASK-0018
Author: Morgan <agent@specops.local>
Rescued-By: Riley <developer@company.com>
Provenance: agent-human-hybrid
"""
And task "TASK-0018" is transitioned from "refined/" to "complete/".
-
```

## Rationale & Compelling Value
- **Adoption**: Overcomes the "all-or-nothing" limitation in naive rescue scripts (`git add -A`), giving human engineers surgical control over what enters the main codebase.
  - **Regular Usage**: Prevents throwing away 80% good work just because an agent added a messy scratchpad or broke one file.
  - **Compelling Value**: Preserves expensive LLM compute investments and maintains immaculate git commit provenance with explicit dual-custody attribution.

---
