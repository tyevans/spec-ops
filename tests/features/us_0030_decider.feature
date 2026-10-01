Feature: Pure Decider Event-Sourced Kernel and SQLite Audit Ledger (US-0030)
  As an autonomous agent or human architect
  I want a pure functional decider and embedded SQLite audit ledger
  So that task transitions maintain state invariants and synchronize seamlessly with the backlog read model

  Scenario: Pure Decider Task State Progression
    Given a TaskDecider initialized with initial empty state
    When the decider receives a ProposeTask command for "TASK-0132"
    Then a TaskProposed event is produced
    And evolving the state with TaskProposed produces a task with status "Proposed"

  Scenario: Embedded SQLite Audit Ledger Synchronization
    Given an initialized project repository with SpecOps configuration
    When a task transition event is appended to the event store
    Then the event is recorded in ".specops/events.db"
    And the corresponding markdown file in "docs/project/backlog/" is synchronized synchronously without data loss
