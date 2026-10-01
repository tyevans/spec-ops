---
id: '0153'
title: Modularity Debt Scoring and Source File Growth Proactive Telemetry
status: Complete
dependencies:
- TASK-0058
- TASK-0139
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
governing_prds:
- PRD-0005
governing_stories:
- US-0017
- US-0018
target_bc: core
---

# TASK-0153: Modularity Debt Scoring and Source File Growth Proactive Telemetry

## Summary
Implement modularity debt scoring and proactive source file growth telemetry (`spec-ops health --modularity [--json]`). Fulfilling ADR-0002 and PRD-0005, this engine tracks the line count velocity of source files across recent commits, calculates modularity decay risk scores, and alerts developers and agents when modules approach the 400-line warning threshold long before hard 500-line invariant violations occur.

## Problem Statement & Context
Waiting for a file to reach 500 lines to fail in CI forces reactive, disruptive emergency refactoring. Developers and autonomous coding agents need proactive early-warning telemetry showing which modules are growing rapidly, their afferent/efferent coupling indices, and recommended decomposition seams before files breach limits.

## Key Requirements & Scope
1. **Modularity Debt Analyzer (`src/spec_ops/core/modularity_debt.py`)**:
   - Computes file line count growth rates across the last $N$ git commits.
   - Calculates modularity health index: combines raw line counts, cyclomatic complexity estimates, and cross-context import coupling.
   - Flags files in the danger zone (350–399 lines) with proactive decomposition recommendations.
2. **Modularity Health CLI**:
   - `spec-ops health --modularity` displays visual ranking of top modularity risks.
   - Supports `--json` for CI/CD metrics integration.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Modularity debt module in `src/spec_ops/core/modularity_debt.py` must stay strictly under 400 lines (ADR-0002).
- **Early-Warning Modularity Invariant (ADR-0002)**: Telemetry must proactively flag files >=350 lines before reaching the 400-line warning or 500-line hard failure.
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/core/modularity_debt.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Computing modularity debt scores across project modules
```gherkin
Given a project repository with source files of varying lengths
When the engineer runs "spec-ops health --modularity"
Then a modularity debt report is displayed
And files approaching 400 lines are flagged with proactive decomposition warnings
```

### Scenario 2: Structured JSON modularity telemetry export
```gherkin
Given active codebase files analyzed for modularity health
When the user executes "spec-ops health --modularity --json"
Then a valid JSON payload containing per-file risk scores and line counts is emitted
And returns exit code 0
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary list of file line counts, calculated modularity risk scores scale monotonically with file length and remain strictly bounded between 0.0 and 100.0.
