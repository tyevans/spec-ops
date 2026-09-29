# ADR-0009: Property-Based Testing with Hypothesis and Mutation Testing with Mutmut

## Status
Accepted

## Context
Traditional example-based testing verifies only explicit happy paths and edge cases anticipated by the developer. Furthermore, high line coverage percentages frequently mask "weak assertions" where code is executed without verifying semantic correctness. In autonomous multi-agent environments, AI coding assistants can produce tautological tests that achieve 100% code coverage while failing to detect subtle logic errors or boundary regressions.

Referencing the verification architecture established in Runefoble (ADR-0008), mission-critical domain logic and state machines require two complementary layers of rigorous verification:
1. **Property-based generative testing** to uncover edge cases across large combinatorial input spaces.
2. **Mutation testing** to verify that the test suite possesses genuine defect-detection power.

## Decision
We adopt **Property-Based Testing with Hypothesis** and **Mutation Testing with Mutmut** across all SpecOps components:

1. **Property-Based Generative Testing with Hypothesis**:
   - Core domain models, markdown parsers, graph algorithms, and health evaluators must maintain generative property tests using `@given(...)`.
   - Key system invariants include:
     - *Parser Round-Trip Invariant*: Any valid markdown specification with frontmatter parses into consistent strongly-typed entities without data loss.
     - *Graph Acyclicity Invariant*: Task dependency graphs remain Directed Acyclic Graphs (DAGs); circular dependencies are detected deterministically.
     - *Invariant Boundary Invariant*: Arbitrary line counts $L$ are deterministically categorized into hard violations ($L > 500$), proactive warnings ($400 \le L \le 500$), or compliant ($L < 400$).
     - *Buffer Capacity Invariant*: Backlog curation never decreases buffer capacity below the lower threshold when eligible candidate tasks exist.

2. **Mutation Testing with Mutmut**:
   - Mutmut injects synthetic mutants (swapping operators, inverting conditionals, mutating constants) into source code.
   - Tests must actively fail to "kill" the mutant.
   - Core modules in `src/spec_ops/core/` and `src/spec_ops/backlog/` must maintain a minimum **80% mutation kill score**.

3. **Behavior-Driven Development (BDD) Alignment**:
   - In accordance with ADR-0006, all user stories (`docs/project/user_stories/accepted/`) articulate user value using Gherkin syntax (`Given / When / Then`).
   - Scenarios are executed via `pytest-bdd` against public frontdoors (CLI commands, public modules) with zero private mocks.

4. **Integration into Definition of Ready (DoR) & Definition of Done (DoD)**:
   - Encoded directly in `AGENTS.md` and enforced by autonomous worker preflight gates.
   - **DoR**: Task must cite governing user story with Gherkin acceptance criteria and identify generative invariants.
   - **DoD**: All blackbox tests pass, Hypothesis property tests pass, BDD scenarios pass, Mutmut kill score meets threshold, and health checks report 0 violations and 0 warnings.

## Consequences
- **Positive**:
  - Eliminates vanity coverage and weak assertion blind spots.
  - Automatically identifies obscure edge cases (Unicode boundaries, empty states, circular links) before feature integration.
  - Validates that tests actively detect bugs rather than just executing code.
- **Negative**:
  - Mutation test runs are computationally intensive; executed targeted on domain modules rather than entire codebases on every quick preflight.
