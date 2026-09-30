Feature: Incremental PRD Delta Decomposition and Non-Destructive Scope Evolution (US-0096)

  Scenario: Decomposing newly added checkable outcomes into incremental delta tasks
    Given an accepted PRD "PRD-0001" that already has 23 completed tasks and linked stories
    And Taylor adds a 6th checkable outcome to "PRD-0001": "Navigating visualizer deep links activates target views"
    When Alex runs "spec-ops prd decompose PRD-0001 --diff"
    Then SpecOps detects that outcomes 1 through 5 already have existing stories and tasks
    And identifies outcome 6 as new scope delta
    And synthesizes only 1 new user story "US-0062" and its corresponding vertical slice tasks
    And existing tasks TASK-0001 through TASK-0023 remain completely unmodified in git.

  Scenario: Preserving existing completed and refined tasks during delta decomposition
    Given an existing backlog where "TASK-0010" is marked "Complete" and "TASK-0012" is "Refined"
    When Alex runs "spec-ops prd decompose PRD-0001 --diff"
    Then the file contents, frontmatter, and file paths of "TASK-0010" and "TASK-0012" remain untouched
    And "docs/project/backlog/PRIORITY.md" only appends the newly created delta tasks to the proposed queue.

  Scenario: Flagging removed or deprecated checkable outcomes
    Given Taylor removes checkable outcome 2 from "PRD-0001" in git
    And outcome 2 is currently linked to pending task "TASK-0015 (Proposed)"
    When Alex runs "spec-ops prd decompose PRD-0001 --diff"
    Then SpecOps warns "Outcome 2 was removed from PRD-0001 but has pending task TASK-0015"
    And prompts the user to either archive TASK-0015 or re-link it to another outcome.
