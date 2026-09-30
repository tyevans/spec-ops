@us_0084
Feature: US-0084 Conventional Commit Slice Classification and Standardized Git Trailer Lineage

  Scenario: Deriving Conventional Commit Type from Task Slice Metadata
    Given a refined task "TASK-0018" with slice type "spike" and title "Evaluate mutmut mutation testing"
    And governing ADRs "ADR-0007, ADR-0009" and governing PRD "PRD-0001"
    When the worker engine creates the final squash commit
    Then the commit subject line is formatted as "spike(task-0018): Evaluate mutmut mutation testing"
    And the commit body contains standard RFC-822 git trailers:
      | Trailer Key    | Trailer Value                                      |
      | SpecOps-Task   | TASK-0018                                          |
      | SpecOps-Slice  | spike                                              |
      | SpecOps-PRD    | PRD-0001                                           |
      | SpecOps-ADR    | ADR-0007, ADR-0009                                 |
      | Provenance     | spec-ops-worker (autonomous)                       |
    And "git log -1 --pretty=full" outputs the structured trailers cleanly.

  Scenario: Bug Fix and Refactoring Slice Commit Formatting
    Given a task "TASK-0021" with slice type "refactor" and title "Decompose worker module into submodules"
    When the worker finalizes and squash-merges the task
    Then the commit subject is formatted as "refactor(task-0021): Decompose worker module into submodules"
    And the trailers verify that "SpecOps-Slice: refactor" is recorded.
