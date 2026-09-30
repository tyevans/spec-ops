@us_0040
Feature: Deep-Linked Visualizer Blast Radius Inspection During Code Review

  Scenario: Launching the visualizer focused on a task entity
    Given an open pull request for "TASK-0009"
    When the engineer executes "spec-ops visualizer --serve --entity TASK-0009"
    Then the local visualizer server starts on port 8787
    And navigating to the URL opens the dashboard with "#entity=TASK-0009" active
    And the 2D graph centers and highlights "TASK-0009" with its immediate upstream stories and downstream dependents
    And the task detail drawer automatically slides open showing full metadata and linked PRDs.

  Scenario: Inspecting bounded context boundary isolation
    Given the engineer is viewing the visualizer detail drawer for "TASK-0009"
    When the engineer inspects the "Target Bounded Context" field
    Then all related tasks belonging to the same bounded context are displayed as filterable pills
    And clicking a bounded context pill filters the graph view to show only nodes within that architectural boundary.
