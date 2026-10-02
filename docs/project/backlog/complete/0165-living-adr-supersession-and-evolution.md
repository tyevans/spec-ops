---
id: '0165'
title: Living Architectural Decision Record Supersession and Evolution Engine
status: Complete
dependencies:
- TASK-0078
- TASK-0158
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
governing_prds:
- PRD-0005
governing_stories:
- US-0106
target_bc: core
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-02T01:06:30.914595+00:00'
commit_signature_status: SIGNED
has_signed_commits: true
---

# TASK-0165: Living Architectural Decision Record Supersession and Evolution Engine

## Summary
Implement a living Architectural Decision Record (ADR) supersession and evolution engine (`src/spec_ops/adrs/supersession.py`). Governed by ADR-0001 and PRD-0005, this engine coordinates the architectural evolution of decision records, scaffolding new replacement ADRs, updating legacy ADR frontmatter (`superseded_by: ADR-XXXX`), and atomically synchronizing `docs/project/adrs/REGISTRY.md` (`spec-ops adr supersede`).

## Problem Statement & Context
As systems mature, initial architectural decisions are superseded by modern architectural choices (e.g. SQLite storage superseding flat JSON files). Updating ADRs manually risks broken references, unsynchronized status values, and inaccurate knowledge graph edges. An automated supersession workflow maintains a pristine, bidirectional audit trail of architectural decisions over time.

## Key Requirements & Scope
1. **ADR Supersession Engine (`src/spec_ops/adrs/supersession.py`)**:
   - Updates target existing ADR: transitions status to `Superseded`, adds `superseded_by: ADR-YYYY` frontmatter and rationale section.
   - Scaffolds new superseding ADR with frontmatter `supersedes: ADR-XXXX`, initial decision context, and consequences.
   - Atomically updates `docs/project/adrs/REGISTRY.md` with accurate statuses.
   - Validates that no circular supersession chains exist (e.g. A supersedes B supersedes A).
2. **ADR Supersession CLI (`spec-ops adr supersede --old <ADR_ID> --title <title> [--dry-run]`)**:
   - Executes supersession and outputs the newly generated ADR path.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Module in `src/spec_ops/adrs/supersession.py` must stay strictly under 400 lines (ADR-0002).
- **Specification as Code (ADR-0001)**: All ADRs are version-controlled Markdown files with valid YAML frontmatter.
- **Mutation Testing Scope**: Target module `src/spec_ops/adrs/supersession.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Superseding an accepted ADR with a new decision
```gherkin
Given an existing accepted ADR in "docs/project/adrs/accepted/"
When the architect runs spec-ops adr supersede with the target ADR ID and new title
Then the old ADR is updated with status Superseded and superseded_by pointer
And a new ADR is created with supersedes pointer
And docs/project/adrs/REGISTRY.md reflects the updated statuses
```

### Scenario 2: Preventing circular supersession references
```gherkin
Given an ADR that already supersedes another decision
When an attempt is made to create a circular supersession cycle
Then the operation is rejected with an error message
And the existing ADR files remain unmodified
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that any sequence of valid supersessions forms a directed acyclic tree of architectural lineage without duplicate IDs or broken file pointers.
