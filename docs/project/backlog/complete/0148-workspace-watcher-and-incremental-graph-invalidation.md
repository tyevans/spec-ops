---
id: 0148
title: Real-Time Workspace File Watcher and Incremental Graph Invalidation Engine
status: Complete
dependencies:
- TASK-0133
- TASK-0142
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0011
- ADR-0015
governing_prds:
- PRD-0005
governing_stories:
- US-0059
- US-0060
target_bc: graph
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T11:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0148: Real-Time Workspace File Watcher and Incremental Graph Invalidation Engine

## Summary
Implement the real-time workspace file watcher and incremental graph invalidation engine (`src/spec_ops/graph/workspace_watcher.py`). Governed by ADR-0011 and ADR-0015, this engine monitors specification and code directories (`docs/project/`, `src/`) for file system events, selectively invalidates only the affected nodes in the content-addressed graph cache (`.specops/cache/graph.json`), and maintains sub-10ms query responsiveness.

## Problem Statement & Context
Full relational graph compilation from scratch takes tens of milliseconds across large repositories. Re-parsing every Markdown and Python file on every query degrades interactive responsiveness in developer visualizers and watch daemons. ADR-0015 mandates content-addressed graph caching with incremental cache invalidation triggered by fine-grained filesystem events.

## Key Requirements & Scope
1. **Incremental Invalidation Engine (`src/spec_ops/graph/workspace_watcher.py`)**:
   - Computes SHA-256 delta hashes for modified or created files.
   - Selectively invalidates and re-extracts only the graph entities and relationships corresponding to modified file paths.
   - Preserves unaffected graph subtrees and transitive reachability caches.
2. **Watch Daemon CLI (`spec-ops graph watch [--interval <sec>] [--debounce-ms <ms>] [--json]`)**:
   - Emits real-time graph invalidation events to stdout or structured JSON.
   - Supports debounced batching of rapid filesystem write bursts.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Watcher module in `src/spec_ops/graph/workspace_watcher.py` must stay strictly under 400 lines (ADR-0002).
- **Sub-10ms Invalidation Invariant (ADR-0015)**: Incremental single-file cache invalidation must execute in under 10 milliseconds.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/graph/workspace_watcher.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Selectively invalidating modified specification entities
```gherkin
Given a warm relational graph cache in ".specops/cache/graph.json"
When a single task specification "docs/project/backlog/refined/TASK-0001.md" is modified
Then the incremental invalidator updates only the entity for "TASK-0001"
And unaffected PRD, persona, and ADR graph entities remain untouched in cache
```

### Scenario 2: Sub-10ms incremental update performance
```gherkin
Given an active workspace watcher monitoring the repository
When a file change event is received
Then the incremental graph update completes in under 10 milliseconds
And emits a structured change event
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary sequence of file change events, incremental graph state matches the state produced by a cold full-compilation from scratch.
