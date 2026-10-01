---
id: '0170'
title: Autonomous Bounded Context Seam Auditor and Cross-Context Coupling Heatmap
status: Refined
dependencies:
- TASK-0085
- TASK-0153
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
---

# TASK-0170: Autonomous Bounded Context Seam Auditor and Cross-Context Coupling Heatmap

## Summary
Implement an autonomous bounded context seam auditor and cross-context coupling heatmap generator (`src/spec_ops/core/seam_auditor.py`). Governed by ADR-0007 and PRD-0005, this engine statically analyzes Python import graphs across domain packages (`core/`, `worker/`, `security/`, `prd/`, `visualizer/`), detects illegal cross-context internal dependencies, and computes afferent/efferent coupling metrics (`spec-ops architecture seams`).

## Problem Statement & Context
As multi-worker swarms develop features rapidly, cross-context dependencies can accidentally leak (e.g. core domain importing private visualizer or rescue internals). This violates Domain-Driven Design bounded context boundaries and creates tangled architectural spaghetti. An automated seam auditor validates architectural layers and enforces strict isolation rules.

## Key Requirements & Scope
1. **Seam Auditor Engine (`src/spec_ops/core/seam_auditor.py`)**:
   - Parses AST imports across all source files in `src/spec_ops/`.
   - Maps each module to its declared bounded context.
   - Evaluates allowed vs forbidden cross-context dependencies (e.g. pure domain models must not import CLI handlers or visualizer templates).
   - Generates coupling metrics: afferent coupling ($Ca$), efferent coupling ($Ce$), and instability index ($I = Ce / (Ca + Ce)$).
2. **Architecture Seams CLI (`spec-ops architecture seams [--strict] [--json] [--export-heatmap <path>]`)**:
   - Displays context coupling matrix and flags unauthorized cross-context imports.
   - When `--strict` is enabled, exits with code 1 if unauthorized leaks exist.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Module in `src/spec_ops/core/seam_auditor.py` must stay strictly under 400 lines (ADR-0002).
- **Domain-Driven Design (ADR-0007)**: Pure domain layers remain completely isolated from presentation or infrastructure layers.
- **Mutation Testing Scope**: Target module `src/spec_ops/core/seam_auditor.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Auditing bounded context import compliance
```gherkin
Given a project repository with clean bounded context separation
When the architect runs spec-ops architecture seams
Then all cross-context imports are verified compliant
And the command terminates with exit code 0
```

### Scenario 2: Flagging illegal cross-context internal import
```gherkin
Given a core domain module directly importing private visualizer internals
When spec-ops architecture seams runs with strict mode
Then the illegal cross-context dependency is flagged
And the command terminates with exit code 1
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary package import graph, computed instability indices are strictly bounded within [0.0, 1.0].
