# ADR-0010: Event-Sourced Core Substrate with eventsource-py

## Status
Accepted

## Context
SpecOps coordinates autonomous software delivery and project management across human architects and parallel AI coding assistants executing in isolated git worktrees. 

Currently, task transitions and worker coordination are implemented imperatively through direct filesystem operations:
1. Moving markdown files between `proposed/`, `refined/`, and `complete/` via `pathlib.Path.rename()`.
2. Re-serializing YAML frontmatter blocks upon status changes.
3. Performing regex string substitutions across `docs/project/backlog/PRIORITY.md`.

This imperative approach exhibits architectural limitations as multi-agent concurrency expands:
- **Loss of Intermediate History & Auditability**: Intermediate states—such as worker task claims, preflight attempt failures, self-healing retries, and timing telemetry—are lost or scattered across raw terminal logs rather than captured in an auditable ledger.
- **Concurrency Hazards**: In high-concurrency environments with $N$ parallel worktrees, coordinating task assignment without optimistic locking risks race conditions.
- **I/O and Domain Logic Entanglement**: Business invariants (e.g., dependency verification, preflight checks, DoR compliance) are intertwined with disk I/O, increasing testing friction and reducing mutation kill efficiency.

`tyevans/eventsource-py` is a production-grade, async-first Python Domain-Driven Design (DDD) and Event Sourcing library providing:
- Pure functional deciders (`DeciderAggregate[State, Command]` with `initial_state`, `decide`, and `evolve`).
- Strongly-typed Pydantic v2 domain events and commands (`DomainEvent`, `DomainCommand`, `EventRegistry`).
- Optimistic concurrency control (`ExpectedVersion`) and pluggable event stores.
- A first-class testing toolkit (`DeciderScenario`, `InMemoryTestHarness`) for pure given/when/then verification without I/O or mocks.
- Projections and subscriptions (`SubscriptionManager`) for folding event streams into diverse read models.

## Decision
We adopt **`eventsource-py` as the foundational domain kernel** for SpecOps task lifecycle and autonomous worker execution:

1. **Pure Decider Domain Core**:
   - The task lifecycle is modeled as a pure `DeciderAggregate` (`TaskDecider`).
   - Invariant validation (`decide(command, state) -> list[DomainEvent]`) and state folding (`evolve(state, event) -> TaskState`) are pure, deterministic functions free of filesystem or network I/O.
   - Core domain commands include: `ProposeTask`, `RefineTask`, `ClaimTask`, `RecordPreflight`, `CompleteTask`, and `ReleaseTask`.
   - Core domain events include: `TaskProposed`, `TaskRefined`, `TaskClaimed`, `TaskPreflightRecorded`, `TaskCompleted`, and `TaskReleased`.

2. **Bounded Context Scoping**:
   - Event sourcing is applied specifically where auditability, state transitions, and concurrency control are business-critical: the **Backlog Task Lifecycle** and **Autonomous Worker Execution** bounded contexts.
   - Higher-level strategic planning artifacts (`Personas`, `PRDs`, `ADRs`) remain git-versioned Markdown documents with YAML frontmatter.

3. **Zero-Daemon Local Substrate & CQRS Projections**:
   - SpecOps maintains its core promise: **zero mandatory external server daemons** (PostgreSQL, Kafka, or Redis are never required for CLI usage).
   - In-memory event stores (`InMemoryEventStore`) and lightweight embedded stores (`SQLiteEventStore` via `aiosqlite` at `.specops/events.db`) serve execution.
   - The git-tracked markdown files under `docs/project/backlog/` and `PRIORITY.md` serve as the **filesystem projection (read model)**. When an event is appended, an inline projection synchronizes the markdown frontmatter and file location synchronously before CLI completion.

4. **Pure Blackbox Verification via DeciderScenario**:
   - All domain state invariants are verified using `eventsource.testing.DeciderScenario` and Hypothesis generative testing (`@given`).
   - This satisfies ADR-0003 (Blackbox Frontdoor Verification) and ADR-0009 (Property and Mutation Testing), achieving high mutant kill rates on domain logic without mocking I/O.

## Consequences
- **Positive**:
  - Eliminates fragile regex-based state synchronizations and filesystem race conditions.
  - Yields an immutable, auditable log of autonomous agent activities, preflight attempts, and task progression.
  - Decouples domain rules from filesystem serialization, drastically speeding up test execution.
  - Pure decider functions provide an ideal target for property-based and mutation testing with `mutmut`.
  - Enables real-time event subscriptions for the TUI dashboard and visualizer.
- **Negative**:
  - Introduces `eventsource-py` (along with `pydantic` and `sqlalchemy`) into production dependencies.
  - Requires maintaining an inline projection layer to keep git-tracked Markdown files synchronized with event-sourced aggregate state.
