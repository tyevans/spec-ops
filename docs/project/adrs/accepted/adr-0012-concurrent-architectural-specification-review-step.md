# ADR-0012: Concurrent Architectural Specification Review Step

## Status
Accepted

## Context
In autonomous development workflows, preflight verification (running tests, linters, and type checkers) validates syntactic correctness and regression avoidance, but cannot evaluate semantic completeness or architectural alignment. Autonomous agents may pass all tests by writing trivial assertions, missing requirements, violating bounded context constraints, or diverging from governing Architectural Decision Records (ADRs).

Conversely, requiring human reviewers or a serial review pass after test runs introduces unnecessary latency and increases iteration cycle times. Furthermore, if an architectural reviewer runs tests or reports syntax and lint errors already caught by CI, effort is duplicated and LLM attention windows are squandered on mechanical errors.

## Decision
We introduce an **Autonomous Architectural Specification Review Step**:
1. **Concurrent CI & Review Execution**: Upon producing code modifications, the worker engine executes CI preflight checks and the architectural reviewer concurrently in isolated threads.
2. **Strict Reviewer Boundaries**: The reviewer is explicitly instructed not to run tests or linters and not to report test/lint failures, as CI preflight runs concurrently to handle those mechanical concerns.
3. **Multi-Faceted Architectural Validation**: The reviewer evaluates the code diff strictly against:
   - Task specification completeness and acceptance criteria coverage.
   - Governing ADRs, PRDs, and user story invariants.
   - Bounded context boundaries and domain isolation (ADR-0007).
   - Anti-rot source file limits (<500 lines per file, ADR-0002).
   - Blackbox frontdoor testing contracts (ADR-0003).
4. **Self-Healing Review Feedback Loop**: If the reviewer requests changes (`STATUS: CHANGES_REQUESTED`), structured actionable feedback is injected into the implementation agent's repair prompt alongside any CI preflight failures, allowing the agent to self-heal and satisfy both gates before integration.
5. **Configurable Execution**: Review can be configured via `[execution] enable_review` and `reviewer_command` in `specops.toml`, and bypassed via `--no-review` / `--skip-review` flags for manual workflows.

## Consequences
- **Positive**: Guarantees that code delivered by autonomous workers is both functionally correct and architecturally aligned; eliminates reviewer fatigue by delegating mechanical checks to CI; reduces total cycle latency through concurrency.
- **Negative**: Adds an LLM inference call per worker iteration when review is enabled.
