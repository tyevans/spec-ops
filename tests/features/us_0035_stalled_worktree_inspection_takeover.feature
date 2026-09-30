Feature: Stalled Autonomous Worktree Inspection and Diagnostic Takeover

  Scenario: Inspecting a stalled agent worktree with diagnostics
    Given an autonomous worker session has exhausted its self-healing attempts on task "TASK-0011"
    And the isolated worktree ".worktrees/task-0011" is preserved with preflight diagnostics in ".task-prompt.md"
    When the engineer executes "spec-ops rescue inspect TASK-0011"
    Then the CLI displays the worktree directory path, git branch, and dirty status
    And the last preflight error diagnostics from ".task-prompt.md" are rendered to the terminal
    And instructions are provided for completing or discarding the rescue.

  Scenario: Human takeover, verification, and atomic merge into main
    Given an inspected worktree for "TASK-0011"
    When the engineer executes "spec-ops rescue takeover TASK-0011"
    Then the task claim is transferred to the human developer and instructions are printed.
    When the engineer executes "spec-ops rescue TASK-0011 --complete"
    Then preflight verification executes inside the worktree
    And upon preflight passing, any uncommitted changes are committed with trailer "SpecOps-Task: TASK-0011"
    And the feature branch is squash-merged into "main" under MERGE_LOCK
    And task "TASK-0011" is moved from "docs/project/backlog/refined/" to "docs/project/backlog/complete/"
    And the isolated worktree directory and branch are cleanly removed.

  Scenario: Discarding an irreparably broken agent worktree
    Given a stalled worktree ".worktrees/task-0099" that is deemed unrecoverable
    When the engineer executes "spec-ops rescue TASK-0099 --discard"
    Then the worktree directory ".worktrees/task-0099" is deleted
    And its associated git branch is deleted
    And task "TASK-0099" remains safely in "docs/project/backlog/refined/" for re-assignment.
