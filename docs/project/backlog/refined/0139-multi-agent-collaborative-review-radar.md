---
id: 0139
title: Multi-Agent Collaborative Review Radar and Cross-Context Interface Auditor
status: Refined
dependencies:
- TASK-0058
- TASK-0114
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
- ADR-0009
governing_prds:
- PRD-0005
governing_stories:
- US-0106
- US-0115
target_bc: core
---

# TASK-0139: Multi-Agent Collaborative Review Radar and Cross-Context Interface Auditor

## Summary
Implement the multi-agent collaborative review radar (`spec-ops review radar [--json] [--bc <context>]`). Analyze pending feature branches, diffs, and worktrees against cross-cutting architectural invariants, bounded context boundaries, and public interface mutations before merge lock acquisition. Surface interface regressions, coupling violations, and unapproved dependency additions across parallel agent workstreams.

## Problem Statement & Context
When parallel autonomous agents execute tasks in isolated worktrees, each agent focuses on its assigned task slice but lacks global awareness of concurrent interface changes in other bounded contexts. Without a pre-merge review radar, parallel workers can introduce conflicting API contracts or cyclic cross-context dependencies that cause runtime breakage only after integration.

## Key Requirements & Scope
1. **Cross-Context Interface Audit (`src/spec_ops/core/review_radar.py`)**:
   - Compares public classes, functions, and CLI options across active branches and worktrees against the `main` baseline AST.
   - Detects breaking interface modifications touching neighboring bounded contexts (`core`, `worker`, `prd`, `rescue`, `scaffold`).
   - Flags circular dependencies between contexts and unapproved external import additions.
2. **Interactive Review Radar Report (`spec-ops review radar`)**:
   - Generates a terminal visual matrix and optional JSON payload.
   - Highlights risk scores, affected interfaces, and governing ADR references.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Review radar module in `src/spec_ops/core/review_radar.py` must stay strictly under 400 lines (ADR-0002).
- **Domain-Driven Design Invariant (ADR-0007)**: Strict enforcement of directional dependencies between bounded contexts (e.g. infrastructure depends on domain, never vice versa).
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/core/review_radar.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Auditing cross-context boundary violations in active worktree diffs
```gherkin
Given an active worktree introducing an import from "infrastructure" into a pure "domain" module
When the engineer runs "spec-ops review radar"
Then an architectural boundary violation is reported citing ADR-0007
And the review radar returns exit code 1
```

### Scenario 2: Clean review radar on compliant interface changes
```gherkin
Given a worktree modifying internal logic within a single bounded context without public API breaks
When the engineer runs "spec-ops review radar"
Then zero cross-context violations are reported
And the radar returns exit code 0
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that any arbitrary AST module diff is partitioned deterministically into public API contracts and private internals without false positives.
