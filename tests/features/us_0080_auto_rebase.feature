Feature: Autonomous Worktree Auto-Rebase and Optimistic Merge Conflict Resolver

  Scenario: Clean automated rebase onto latest main tip
    Given an active worktree whose branch is 2 commits behind "main"
    When the worker executes "spec-ops worker rebase TASK-0147"
    Then the worktree branch is rebased cleanly onto "main"
    And the worktree working directory remains clean

  Scenario: Safe conflict abort with diagnostic handover generation
    Given an active worktree with conflicting changes against "main"
    When the worker executes "spec-ops worker rebase TASK-0147"
    Then the conflicting rebase is safely aborted
    And a conflict diagnostic summary is generated in "HANDOVER.md"
