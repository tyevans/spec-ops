---
id: '0136'
title: Selective Worktree Patch Takeover and Partial File Salvage Engine
status: Complete
dependencies:
- TASK-0104
- TASK-0114
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0005
- ADR-0009
governing_prds:
- PRD-0004
governing_stories:
- US-0088
target_bc: rescue
---

# TASK-0136: Selective Worktree Patch Takeover and Partial File Salvage Engine

## Summary
Implement selective patch takeover and partial file salvage (`spec-ops rescue salvage <task-id> --files <paths>` and `spec-ops rescue patch <task-id> --include <file>`) allowing human developers to cherry-pick working source modules and tests from stalled worktrees while discarding hallucinated scrap or bloated modules. Run preflight verification strictly on curated staging areas and squash-merge into `main` under `MERGE_LOCK` with dual-custody provenance trailers.

## Problem Statement & Context
When an autonomous worker stalls, 80% of its generated code may be valid domain logic, while 20% contains hallucinations, broken scratch files, or bloated modules exceeding file length limits. Naive `git add -A` inherits the messy baggage, while abandoning the worktree throws away progress. Developers need a CLI mechanism to cherry-pick only high-quality files from a stalled worktree, validate them with preflight checks, and merge them cleanly into `main` with dual-custody attribution.

## Key Requirements & Scope
1. **Selective File Salvage & Patch Staging (`src/spec_ops/rescue/salvage.py`)**:
   - `spec-ops rescue salvage <task-id> --files <paths>` creates a clean human rescue branch (`rescue/<task-id>`) and stages only the explicitly chosen files.
   - `spec-ops rescue patch <task-id> --include <file>` incrementally stages files into the rescue index.
   - Untracked scratch files and unselected bloated modules remain uncommitted and excluded from preflight verification.
2. **Curated Preflight Validation**:
   - `spec-ops rescue finish <task-id> --salvage` executes preflight verification solely against the curated staging area.
   - Validates file length invariants (<500 lines) and blackbox frontdoor tests.
3. **Squash-Merge with Dual-Custody Provenance Trailers**:
   - Upon preflight passing, merges into `main` under `MERGE_LOCK`.
   - Embeds commit trailers: `SpecOps-Task: TASK-XXXX`, `Author: Morgan <agent>`, `Rescued-By: Riley <developer>`, `Provenance: agent-human-hybrid`.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: New salvage module in `src/spec_ops/rescue/salvage.py` must stay strictly under 400 lines (ADR-0002).
- **Strict Backlog Isolation (ADR-0005)**: Feature and rescue branches never edit `docs/project/backlog/` directly.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/rescue/salvage.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Selectively cherry-picking valid domain files while discarding hallucinated scrap
```gherkin
Given a stalled worktree ".worktrees/task-0018" with valid domain models and unselected bloated scratch files
When the developer executes "spec-ops rescue patch TASK-0018 --include src/spec_ops/core/models.py"
Then only "src/spec_ops/core/models.py" is staged into the rescue changeset
And untracked scratch files remain excluded from preflight and commit staging
```

### Scenario 2: Squash-merging salvaged patch with dual-custody trailers
```gherkin
Given preflight verification passes on the salvaged rescue staging area
When the rescue manager merges the branch into "main" under MERGE_LOCK
Then the commit message includes "Provenance: agent-human-hybrid"
And task "TASK-0018" is transitioned to "complete/" atomically
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary list of selected file paths, only the specified paths are staged into the git index and all unselected files remain untouched.
