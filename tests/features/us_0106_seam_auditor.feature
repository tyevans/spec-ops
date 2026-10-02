Feature: Autonomous Bounded Context Seam Auditor and Cross-Context Coupling Heatmap

  Scenario: Auditing bounded context import compliance
    Given a project repository with clean bounded context separation
    When the architect runs spec-ops architecture seams
    Then all cross-context imports are verified compliant
    And the command terminates with exit code 0

  Scenario: Flagging illegal cross-context internal import
    Given a core domain module directly importing private visualizer internals
    When spec-ops architecture seams runs with strict mode
    Then the illegal cross-context dependency is flagged
    And the command terminates with exit code 1
