@us_0084 @rescue @failure_clustering
Feature: Autonomous Failure Post-Mortem Clustering and Prompt Anti-Loop Synthesizer

  Scenario: Clustering recurrent failure modes across tasks
    Given multiple backlog tasks with recorded failure histories citing mock backdoors
    When the failure clustering engine analyzes the backlog
    Then a common failure cluster for "Mock Backdoor Tampering" is identified
    And associated with ADR-0003

  Scenario: Hydrating prompt with synthesized negative constraints
    Given an identified failure cluster for mock backdoors
    When a new worker claims a related task
    Then the generated ".task-prompt.md" includes explicit negative prompt instructions forbidding mocks
