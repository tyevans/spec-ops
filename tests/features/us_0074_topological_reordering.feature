Feature: US-0074 Deterministic Multi-Criteria Priority Re-Ranking and Topological Backlog Ordering

  Scenario: Topological Re-ordering to Resolve Priority Inversion
    Given task "TASK-0005" depends on task "TASK-0012"
    And in "PRIORITY.md", "TASK-0005" is listed at position 4 while "TASK-0012" is listed at position 15
    When the architect runs "spec-ops backlog reorder --topological"
    Then the re-ranking algorithm detects the priority inversion
    And reorders "PRIORITY.md" so that prerequisite "TASK-0012" strictly precedes dependent "TASK-0005"
    And verifies 0 circular dependency cycles before writing the updated index.

  Scenario: Multi-Criteria Weighted Priority Scoring (Milestone, Blocker Count, Impact)
    Given proposed task "TASK-0040" blocks 5 downstream tasks in "Milestone 2"
    And proposed task "TASK-0041" blocks 0 downstream tasks in "Milestone 3"
    When the architect runs "spec-ops backlog reorder --by-weights"
    Then "TASK-0040" is assigned a higher priority rank than "TASK-0041" based on downstream fan-out weight and target milestone deadline
    And "PRIORITY.md" reflects the updated sequential ordering.

  Scenario: Respecting Architect Pin Overrides during Reordering
    Given task "TASK-0008" contains "priority_pin: 1" in its YAML frontmatter
    When the architect runs "spec-ops backlog reorder"
    Then "TASK-0008" remains locked at position 1 in "PRIORITY.md"
    And all other unpinned tasks are sorted topologically around it without violating prerequisite constraints.
