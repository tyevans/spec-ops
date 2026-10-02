Feature: Autonomous Failure Memory Strategy Indexer and Healing Playbook Generator

  Scenario: Indexing failure post-mortems and generating healing strategies
    Given a history of resolved worktree failures and post-mortem logs
    When the strategy indexer compiles the healing playbook
    Then categorized failure strategies are produced with actionable remedies
    And the command terminates with exit code 0

  Scenario: Retrieving targeted strategy for specific error signature
    Given an indexed strategy database containing file limit remediation advice
    When a worker queries the playbook for "ADR-0002" failure signatures
    Then the matching decomposition strategy is returned with guidance
