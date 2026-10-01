Feature: Deterministic DAG Cycle Resolution and Choke Point Pruning Engine

  Scenario: Resolving multi-node circular dependency with minimal feedback edge detection
    Given a backlog with cyclic tasks:
      | id        | dependencies |
      | TASK-0010 | [TASK-0011]  |
      | TASK-0011 | [TASK-0012]  |
      | TASK-0012 | [TASK-0010]  |
    When the lead runs "spec-ops graph cycles --resolve"
    Then the command exits with code 1
    And reports "Cyclic Backlog Dependency Detected: Strongly Connected Component of size 3"
    And prints the directed cycle path: "TASK-0010 -> TASK-0011 -> TASK-0012 -> TASK-0010"
    And pinpoints minimal feedback edge: "(TASK-0012, TASK-0010)"
    And outputs actionable cycle remediation: "Break cycle by removing dependency from TASK-0012 to TASK-0010"

  Scenario: Identifying transitive choke point bottlenecks and suggesting decoupling seams
    Given a backlog with high-fanout choke points:
      | id        | dependencies |
      | TASK-0001 | []           |
      | TASK-0002 | [TASK-0001]  |
      | TASK-0003 | [TASK-0001]  |
      | TASK-0004 | [TASK-0002]  |
    When the lead runs "spec-ops graph cycles --prune-chokepoints"
    Then the command exits with code 0
    And reports "Traceability Invariant Met: Zero dependency cycles detected."
    And identifies choke point "TASK-0001"
    And suggests decoupling seams for "TASK-0001"

  Scenario: Structured JSON export of cycle resolution and choke points
    Given a backlog with cyclic tasks:
      | id        | dependencies |
      | TASK-0020 | [TASK-0021]  |
      | TASK-0021 | [TASK-0020]  |
    When the lead runs "spec-ops graph cycles --resolve --prune-chokepoints --json"
    Then the command exits with code 1
    And the JSON output contains cyclic status true
    And the JSON output contains cycle resolution feedback edges
    And the JSON output contains choke points
