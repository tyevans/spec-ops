Feature: Full Bidirectional Graph Traceability and Orphan Work Item Audit

  Scenario: Clean repository passing bidirectional graph verification
    Given a repository where all tasks cite accepted stories, all stories cite accepted PRDs, and all PRDs cite valid personas
    When the architect runs "spec-ops trace --verify"
    Then the command exits with code 0
    And reports "Traceability Invariant Met: 100% graph connectivity with 0 orphan entities".

  Scenario: Detecting an orphaned task with a non-existent story link
    Given a task file in "docs/project/backlog/proposed/0030-orphan-feature.md" citing "story: US-9999"
    And "US-9999" does not exist in "docs/project/user_stories/"
    When the architect runs "spec-ops trace --verify"
    Then the command exits with code 1
    And reports "Graph Error: Task 0030-orphan-feature references missing story 'US-9999'".

  Scenario: Detecting cyclical task dependencies in the backlog graph
    Given task "TASK-0010" has "dependencies: [TASK-0011]"
    And task "TASK-0011" has "dependencies: [TASK-0010]"
    When the architect runs "spec-ops trace --verify"
    Then the command exits with code 1
    And reports "Cyclic Backlog Dependency Detected: TASK-0010 <-> TASK-0011"
    And outputs the cycle path.
