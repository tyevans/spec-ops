@us_0048 @traceability @persona
Feature: US-0048 Persona-to-Commit Bidirectional Traceability Matrix and Coverage Auditor

  Scenario: Inspecting Full Lineage for a Customer Persona
    Given documented personas in "PERSONAS.md" and linked stories across the backlog
    When Taylor selects "Persona: Taylor" in the visualizer Traceability Matrix
    Then the interface renders a multi-column lineage view:
      | Persona | PRD      | User Story | Backlog Task | Git Commit | Status   |
      | Taylor  | PRD-0001 | US-0006    | TASK-0008    | abc1234    | Complete |
      | Taylor  | PRD-0001 | US-0009    | TASK-0013    | def5678    | Complete |
    And clicking any node in the lineage chain highlights its connections across the entire project graph.

  Scenario: Auditing Persona Coverage and Highlighting Neglected Customer Segments
    Given the project has active tasks in "proposed/" and "refined/"
    When Taylor executes "spec-ops stats --persona-coverage" or views the Persona Studio
    Then a coverage distribution report is displayed showing task allocation per persona
    And warns when a persona has 0 active stories in the current milestone
    And flags any backlog task lacking a governing user story or persona lineage as an "Orphan Task".

  Scenario: Instant Stakeholder Query Resolution via Shareable Permalinks
    Given Taylor receives an inquiry from leadership asking about progress on "Living 2D Graph Visualizer"
    When Taylor filters the Traceability Matrix by "FEAT-VIS-01"
    And clicks "Copy Shareable Link"
    Then the clipboard receives a deep link permalink with URL state "#tab=prds&entity=PRD-0001&filter=FEAT-VIS-01"
    And recipient opening the URL sees the exact filtered lineage and delivery progress without logging in.
