Feature: Supply-Chain Lockfile Mutation Sentinel and Pre-Execution Hook (US-0028, TASK-0127)

  Scenario: Autonomous Agent Lockfile Mutation Blocked by Sentinel
    Given an isolated worktree with protected lockfiles
    When an autonomous worker modifies "uv.lock" without an approved waiver
    And the sentinel checks the worktree state
    Then the lockfile sentinel blocks the execution with a violation
    And identifies "uv.lock" as an unauthorized mutation

  Scenario: Automatic Remediation of Lockfile Mutation with Fix Flag
    Given an isolated worktree with protected lockfiles
    When an autonomous worker modifies "package-lock.json" without an approved waiver
    And the sentinel runs with "--fix"
    Then the unauthorized mutation is reverted
    And the worktree returns to a clean valid state

  Scenario: Authorized Lockfile Mutation Permitted with Approved Waiver
    Given an isolated worktree with an approved waiver
    When an autonomous worker modifies "requirements.txt"
    And the sentinel checks the worktree state
    Then the lockfile sentinel allows the modification
    And reports that the waiver was applied
