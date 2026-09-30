@us_0092 @prune @rescue
Feature: Zero-Pollution Worktree Garbage Collection and Orphan Pruning

  Scenario: Detecting and safely pruning worktrees of completed tasks
    Given worktree directory ".worktrees/task-0005" exists on disk
    And task "TASK-0005" is already marked "complete" in "docs/project/backlog/complete/"
    When the engineer executes "spec-ops rescue prune"
    Then the CLI identifies ".worktrees/task-0005" as an orphaned completed worktree
    And safely runs "git worktree remove --force .worktrees/task-0005"
    And deletes the merged local branch "feat/TASK-0005"
    And executes "git worktree prune".

  Scenario: Guarding active and dirty human rescue worktrees from accidental deletion
    Given worktree directory ".worktrees/task-0016" has uncommitted local changes authored by the engineer
    And task "TASK-0016" remains in "docs/project/backlog/refined/"
    When the engineer executes "spec-ops rescue prune"
    Then the CLI skips ".worktrees/task-0016"
    And displays a protection warning:
      """
      Skipping .worktrees/task-0016: Worktree is dirty with active human modifications. Run 'spec-ops rescue reset TASK-0016' to force discard.
      """

  Scenario: Dry-run preview of reclaimable disk space and dangling branches
    Given 4 stale worktrees totaling 1.2 GB of disk space
    When the engineer executes "spec-ops rescue prune --dry-run"
    Then no filesystem modifications are made
    And the CLI prints a table of candidates for pruning, their branch names, and estimated reclaimable space.
