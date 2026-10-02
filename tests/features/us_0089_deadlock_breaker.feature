Feature: Multi-Agent Task Dependency Graph Deadlock Resolver and Cycle Auto-Break Engine

  Scenario: Detecting circular task dependencies and proposing edge breaks
    Given a backlog task graph containing a cyclic dependency between Task A and Task B
    When the deadlock breaker analyzes the graph
    Then the circular dependency cycle is identified
    And a minimal edge removal recommendation is generated
    And the command terminates with exit code 1

  Scenario: Verifying an acyclic dependency graph
    Given a backlog task graph with valid topological ordering and zero cycles
    When the deadlock breaker analyzes the graph
    Then the graph is confirmed acyclic
    And exits with code 0
