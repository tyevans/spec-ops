@us_0081 @rescue
Feature: Automated Worktree Stash and Clean Reset Recovery Engine

  Scenario: Safely stashing uncommitted changes and resetting worktree
    Given a dirty worktree with uncommitted file modifications
    When the developer runs spec-ops rescue reset with stash flag
    Then the uncommitted modifications are archived to a rescue stash
    And the worktree is cleanly reset to pristine HEAD state
    And exits with code 0

  Scenario: Preserving stashed changes across resets
    Given a previously created rescue stash for a worktree
    When the developer inspects available rescue archives
    Then the stash details, timestamp, and diff summary are visible
    And can be selectively reapplied
