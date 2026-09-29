---
id: '0064'
title: Core Domain Mutation Testing Invariant and Mutant Kill Score Quality Gate
status: Accepted
created: 2026-09-29
persona: Jordan (The AI-Native Engineering Lead)
feature: FEAT-CORE-06
governing_prd: PRD-0005
---

# US-0064 — Core Domain Mutation Testing Invariant and Mutant Kill Score Quality Gate

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** AI-native engineering lead,
  - **I want** `spec-ops invariants verify-mutations` to enforce a hard >=80% mutant kill score invariant on `src/spec_ops/core/` using Mutmut,
  - **So that** AI coding assistants and human contributors cannot pass test suites with "weak assertions" or vanity coverage that fail to detect mutations in graph linking, cycle detection, or AST parsing.

## Acceptance Criteria

```gherkin
Scenario: Passing the mutation quality gate on core domain modules
Given the test suite covers all public methods of "src/spec_ops/core/"
When the lead runs "spec-ops invariants verify-mutations --threshold 80"
Then Mutmut injects synthetic mutants into "models.py", "parser.py", and "graph.py"
And tests kill at least 80% of all generated mutants
And the command exits with code 0
And reports "Mutation Invariant Met: 84% mutant kill score (168 killed, 32 survived, 0 timed out)".
```
```gherkin
Scenario: Blocking pull request when weak assertions leave surviving mutants below threshold
Given a pull request modifies "src/spec_ops/core/graph.py" adding a new edge filtering option
And the author adds tests that execute the code but make no assertions on the filtered edge types
When CI executes "spec-ops invariants verify-mutations --threshold 80"
Then Mutmut detects 12 surviving mutants in the unasserted filter branch
And the mutant kill score drops to 71% (below the 80% invariant threshold)
And the command exits with code 1
And prints surviving mutant diffs and exact line numbers requiring stronger blackbox assertions.
```
```gherkin
Scenario: Generating machine-readable mutation score report for CI telemetry
Given a completed mutation test run on "src/spec_ops/core/"
When the lead runs "spec-ops invariants verify-mutations --json"
Then the command outputs valid JSON containing:
- "target_module": "src/spec_ops/core"
- "mutation_score": 84.2
- "threshold": 80.0
- "killed_count": 168
- "survived_count": 32
- "survived_mutants": list of mutant IDs with source code line numbers.
-
```

## Rationale & Compelling Value
- **Adoption**: Eliminates the "false sense of security" created by 100% line coverage where tests execute code without actually asserting semantic correctness.
  - **Regular Usage**: Enforced in CI on all PRs modifying `src/spec_ops/core/` before code can merge into `main`.
  - **Compelling Value**: SaaS tools and traditional workflows judge test quality solely by code coverage. SpecOps mandates mutation testing (ADR-0009) to guarantee tests actively detect defects, making the core data layer resilient against autonomous agent hallucinations.

---
