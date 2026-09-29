Feature: Concurrent Architectural Task Review and Feedback Loop
  As an autonomous engineering team lead and coding worker
  I want an architectural review step executed concurrently with CI preflight
  So that code changes are verified against task specifications and project ADRs and refined via agent feedback loops

  Scenario: Worker executes concurrent CI preflight and architectural review successfully
    Given an initialized SpecOps project with an isolated task worktree
    When the worker executes the task with concurrent CI preflight and architectural review
    Then both CI preflight and architectural review approve the implementation
    And the task modifications are verified cleanly

  Scenario: Implementation agent repairs code from architectural review feedback
    Given an isolated task worktree where reviewer requests changes on attempt 1
    When the worker feeds review feedback into the implementation agent repair loop
    Then the agent resolves the review feedback on attempt 2
    And the task passes review and preflight verification
