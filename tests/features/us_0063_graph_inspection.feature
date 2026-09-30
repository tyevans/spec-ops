Feature: Terminal Graph Inspection, Reachability Pathfinding, and Blast-Radius Traversal

  Scenario: Inspecting an entity's direct graph neighborhood and lineage
    Given a repository where task "TASK-0042" is governed by "ADR-0003", implements "US-0020", and targets bounded context "invariants"
    When the developer runs "spec-ops graph inspect TASK-0042"
    Then the command outputs an ASCII entity card displaying:
      | Field            | Value                         |
      | Entity ID        | TASK-0042                     |
      | Type             | Task (Refined)                |
      | Target BC        | invariants                    |
      | Governing ADRs   | ADR-0003                      |
      | Governing Story  | US-0020                       |
      | Persona Lineage  | Jordan (via US-0020)          |
    And lists all 1st-degree upstream dependencies and downstream dependents.

  Scenario: Finding the shortest traceability path between a customer persona and a git commit
    Given persona "taylor" desires story "US-0046"
    And story "US-0046" specifies PRD "PRD-0001"
    And PRD "PRD-0001" is implemented by task "TASK-0046"
    And commit "a1b2c3d" contains git message "feat: uat matrix (TASK-0046)"
    When the developer runs "spec-ops graph path --from persona:taylor --to commit:a1b2c3d"
    Then the command exits with code 0
    And prints the directed shortest path:
      """
      persona:taylor
      └──[desires]──> story:US-0046
      └──[implements]──> task:TASK-0046
      └──[committed_in]──> commit:a1b2c3d
      Path length: 3 hops.
      """

  Scenario: Calculating downstream blast radius of an ADR before superseding it
    Given ADR "ADR-0003" governs 8 active backlog tasks across 3 bounded contexts
    When the developer runs "spec-ops graph blast-radius ADR-0003"
    Then the command outputs:
      """
      Blast Radius for ADR-0003:
      - 8 governing tasks: [TASK-0002, TASK-0020, TASK-0042, ...]
      - 3 affected bounded contexts: [core, invariants, visualizer]
      - 2 active pull requests: [#104, #112]
      Total Downstream Impact: HIGH (13 nodes affected)
      """
