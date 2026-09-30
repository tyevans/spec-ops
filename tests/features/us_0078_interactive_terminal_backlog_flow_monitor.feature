@us_0078 @tui
Feature: Interactive Terminal Backlog Flow Monitor and JIT Buffer Telemetry

  Scenario: Visualizing Live JIT Buffer Waterline and Worker Telemetry in TUI
    Given a backlog containing 18 completed tasks, 7 refined tasks, 5 proposed tasks, and 2 active agent worktrees
    When the developer executes "spec-ops backlog flow"
    Then a full-screen terminal UI displays three synchronized columns: Proposed, Refined (Buffer: 7/10 [Yellow]), and In-Flight Worktrees
    And displays active worker branch names, elapsed times, and last preflight status
    And updates live without flickering when tasks transition state on disk.

  Scenario: Single-Keystroke Ergonomic Task Promotion from TUI
    Given the developer has navigated to proposed task "TASK-0021" in the Proposed column
    And "TASK-0021" satisfies Definition of Ready rules
    When the developer presses key "r" (Refine)
    Then SpecOps promotes "TASK-0021" to "docs/project/backlog/refined/"
    And atomically updates "PRIORITY.md"
    And the Refined buffer gauge updates from 7/10 to 8/10 [Green].

  Scenario: Single-Keystroke Worktree Provisioning and Claiming for Human IC
    Given a refined task "TASK-0022" highlighted in the Refined column
    When the developer presses key "c" (Claim & Worktree)
    Then SpecOps provisions ".worktrees/task-0022" on branch "feat/task-0022"
    And sets "claimed_by: riley" in task frontmatter
    And opens a subshell in the new worktree directory.
