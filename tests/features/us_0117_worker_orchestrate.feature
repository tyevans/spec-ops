@us-0117 @worker @orchestrator
Feature: Autonomous Multi-Agent In-Worktree Orchestrator & Peer Consultation
  As an AI-native engineering lead and autonomous worker orchestrator
  I want multi-agent task execution to consult approved specifications, conduct peer reviews, and self-heal preflight failures
  So that quality invariants and bounded context integrity are preserved before commit staging.

  Scenario: In-Worktree Subagent Peer Consultation
    Given an implementation subagent working in an isolated worktree on "TASK-0114"
    When the subagent defines an interface change touching another bounded context
    Then the orchestrator peer review inspects the interface against active ADRs
    And provides actionable feedback to the implementation agent before commit staging.

  Scenario: Preflight Verification and Self-Healing
    Given an in-worktree file length invariant failure exceeding 500 lines
    When preflight verification and AST self-healing analyzer executes
    Then actionable AST decomposition hints are generated for iterative self-healing up to max attempts.

  Scenario: Frontdoor Worker Orchestrate CLI Execution
    Given a task ready for execution
    When running the CLI command "spec-ops worker orchestrate" with "--dry-run --json"
    Then the command exits cleanly with valid structured JSON
    And the output confirms active spec consultation and formatted git trailers.
