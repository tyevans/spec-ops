@us_0038 @worktree @sandboxing
Feature: Zero-Toil Human Worktree Sandboxing for Focused Feature Development

  Scenario: Spawning a clean human development worktree
    Given a refined task "TASK-0021" in "docs/project/backlog/refined/"
    When the engineer executes "spec-ops worktree start TASK-0021"
    Then a new git worktree is created at ".worktrees/task-0021"
    And a dedicated branch "feat/TASK-0021" is checked out
    And local workspace environment symlinks and configs are initialized in the worktree
    And the command outputs the command to enter the workspace: "cd .worktrees/task-0021".

  Scenario: Preflight verification and completion from within the worktree
    Given the engineer is inside ".worktrees/task-0021" and has implemented the task
    When the engineer executes "spec-ops worktree finish"
    Then local preflight verification runs across tests, invariants, and linting
    And upon preflight success, changes are pushed or squash-merged into "main" under MERGE_LOCK
    And task "TASK-0021" is advanced to "complete/"
    And the working directory is safely returned to the repository root.
