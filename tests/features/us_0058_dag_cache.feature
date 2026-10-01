Feature: Incremental DAG Topological Cache and Fast Tarjan Cycle Pre-Check
  As a developer or autonomous agent
  I want fast, cached topological sorting and zero-latency cycle pre-checks
  So that queue operations and dependency updates remain sub-millisecond

  Scenario: Fast cycle pre-check rejecting circular dependencies
    Given a cached task dependency DAG where "TASK-0002" depends on "TASK-0001"
    When a command attempts to add "TASK-0001" as a dependency of "TASK-0002"
    Then the cycle pre-check rejects the dependency in under 5 milliseconds
    And reports the exact cyclic path "TASK-0001 -> TASK-0002 -> TASK-0001"

  Scenario: Preserving cached topological execution tiers
    Given an unmodified repository with valid topological cache
    When the queue engine requests execution tiers
    Then tiers are retrieved directly from cache without full repository graph parsing
