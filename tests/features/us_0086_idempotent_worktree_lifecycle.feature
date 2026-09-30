@us_0086 @worktree @rescue
Feature: Idempotent Worktree Lifecycle Management and Stale Worktree Reconciliation

  Scenario: Idempotent Worktree Creation with Branch Collision Recovery
    Given an orphaned worktree directory ".worktrees/task-0009" left from an aborted process
    And a stale local git branch "feat/task-0009" already exists
    When the worker engine prepares to execute "TASK-0009"
    Then the engine inspects the existing worktree for uncommitted human rescue work
    And if uncommitted changes do not exist, prunes stale git worktree administrative metadata via "git worktree prune"
    And resets the branch to "main" before mounting the fresh worktree
    And creates the worktree cleanly without throwing git branch conflict errors.

  Scenario: Atomic Teardown and Resource Cleanup upon Task Finalization
    Given an active worktree at ".worktrees/task-0016" with passing preflight
    When the task is successfully squash-merged into "main"
    Then the worker engine removes the worktree via "git worktree remove --force"
    And deletes the transient branch "feat/task-0016"
    And deletes temporary prompt files and ephemeral worktree caches
    And verifies that ".worktrees/task-0016" no longer exists on disk.
