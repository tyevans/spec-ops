---
id: '0171'
title: Autonomous Failure Memory Strategy Indexer and Healing Playbook Generator
status: Refined
dependencies:
- TASK-0053
- TASK-0144
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0004
- ADR-0020
governing_prds:
- PRD-0004
- PRD-0006
governing_stories:
- US-0085
- US-0117
target_bc: rescue
---

# TASK-0171: Autonomous Failure Memory Strategy Indexer and Healing Playbook Generator

## Summary
Implement a failure memory strategy indexer and automated healing playbook generator (`src/spec_ops/rescue/strategy_indexer.py`). Governed by ADR-0020 and ADR-0004, this engine indexes recurring preflight failure patterns (such as AST diagnostic traces, timeout clusters, and missing fixtures) into categorized resolution strategies and generates actionable healing playbooks for retry loops (`spec-ops rescue playbooks`).

## Problem Statement & Context
When autonomous agents repeatedly encounter similar failure patterns across worktrees, resolving them from scratch wastes compute and time. By indexing past successful post-mortem remediations into a searchable strategy memory store, workers facing familiar failure signatures can immediately retrieve proven healing actions and avoid unproductive retry loops.

## Key Requirements & Scope
1. **Strategy Indexer Engine (`src/spec_ops/rescue/strategy_indexer.py`)**:
   - Parses recorded failure post-mortems from `.specops/failures/` or SQLite event ledger.
   - Extracts failure signatures (exception types, failing modules, rule IDs).
   - Correlates successful recovery steps with failure categories.
   - Generates ranked healing strategies with concrete code snippets and prompt instructions.
2. **Healing Playbook CLI (`spec-ops rescue playbooks [--query <pattern>] [--json] [--export <path>]`)**:
   - Displays available remediation strategies for a given failure signature.
   - Outputs machine-readable JSON playbooks for subagent prompt injection.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Module in `src/spec_ops/rescue/strategy_indexer.py` must stay strictly under 400 lines (ADR-0002).
- **Anti-Loop Memory (ADR-0020)**: Preserves version-controlled remediation records.
- **Mutation Testing Scope**: Target module `src/spec_ops/rescue/strategy_indexer.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Indexing failure post-mortems and generating healing strategies
```gherkin
Given a history of resolved worktree failures and post-mortem logs
When the strategy indexer compiles the healing playbook
Then categorized failure strategies are produced with actionable remedies
And the command terminates with exit code 0
```

### Scenario 2: Retrieving targeted strategy for specific error signature
```gherkin
Given an indexed strategy database containing file limit remediation advice
When a worker queries the playbook for "ADR-0002" failure signatures
Then the matching decomposition strategy is returned with guidance
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that indexing arbitrary failure logs produces deterministic strategy rankings without duplicate strategy IDs or corrupted markdown formatting.
