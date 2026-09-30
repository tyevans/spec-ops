@us_0106 @visualizer @architecture
Feature: Living Architectural Review Radar and Bounded Context Dependency Audit

  Scenario: Bounded Context Boundary and Dependency Flow Inspection
    Given a project with explicit bounded contexts: "core", "visualizer", "reporting", "worker", "health"
    When Alex selects the "ADR Architecture" tab and switches layout to "Radar" or "Flow DAG"
    Then the visualization groups entities into distinct bounded context clusters with color-coded boundaries
    And directed edges illustrate dependency flows between contexts
    And any illegal backward dependency violating ADR-0007 is highlighted with a pulsing red warning line.

  Scenario: ADR Supersession Lineage and Active Status Radar
    Given an architectural record "ADR-0005" that has been superseded by "ADR-0014"
    When Alex inspects "ADR-0005" in the visualizer ADR Matrix
    Then "ADR-0005" is visually rendered with a strikethrough badge "Superseded"
    And the detail drawer displays a prominent notification: "Superseded by ADR-0014: Worktree Concurrency v2"
    And clicking the supersession link navigates directly to "ADR-0014" with updated consequences and active invariants.

  Scenario: Automated Orphan Work Item and Specification Drift Audit
    Given a project containing:
      | type  | count | description                                         |
      | task  | 1     | 1 backlog task with no governing PRD or User Story   |
      | story | 1     | 1 user story with no linked PRD                     |
      | prd   | 1     | 1 PRD with zero implementing tasks                  |
    When Alex clicks "Audit Specification Drift" in the visualizer header
    Then an audit modal opens categorizing all orphaned specifications
    And each orphan entity provides a 1-click action to scaffold missing governing specs or archive obsolete entries
    And Alex can export the audit report as "dist/spec-drift-audit.json".
