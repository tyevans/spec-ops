@us_0077 @backlog @milestone @rollover
Feature: Milestone Scope Transition and Rollover Engine
  As an AI-native engineering lead,
  I want to run "spec-ops milestone rollover --from <M_SRC> --to <M_DST>",
  So that unfinished tasks from completed milestones are systematically transitioned to the next target milestone with atomic frontmatter updates.

  Scenario: Transitioning Backlog Scope Across Milestone Boundaries
    Given a repository with completed tasks in "complete/" and unfinished tasks in "refined/" and "proposed/" assigned to milestone "M1"
    When the lead runs "spec-ops milestone rollover --from M1 --to M2"
    Then unfinished tasks are reassigned to milestone "M2"
    And milestone tags in frontmatter are atomically updated
    And completed tasks in "complete/" remain untouched.

  Scenario: Previewing Milestone Rollover in Dry Run Mode
    Given a repository with completed tasks in "complete/" and unfinished tasks in "refined/" and "proposed/" assigned to milestone "M1"
    When the lead runs "spec-ops milestone rollover --from M1 --to M2 --dry-run"
    Then candidate tasks are listed in the output
    And no task files on disk are modified.

  Scenario: Milestone Rollover Output as Structured JSON
    Given a repository with completed tasks in "complete/" and unfinished tasks in "refined/" and "proposed/" assigned to milestone "M1"
    When the lead runs "spec-ops milestone rollover --from M1 --to M2 --json"
    Then the output is valid JSON reporting the transitioned tasks and count
    And unfinished tasks are reassigned to milestone "M2"
