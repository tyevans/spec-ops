Feature: Living Visualizer Lead Console with Real-Time Agent Fleet Telemetry

  Scenario: Live Agent Fleet and Worktree Telemetry
    Given multiple autonomous workers running across isolated git worktrees
    When the lead navigates to the "Lead Console" tab in the visualizer
    Then an active fleet status grid displays:
      | Task ID   | Worktree Path             | Branch          | Status       | Attempt | Active Preflight Check |
      | TASK-0013 | .worktrees/task-0013      | feat/task-0013  | Executing    | 1/3     | uv run pytest          |
      | TASK-0014 | .worktrees/task-0014      | feat/task-0014  | Self-Healing | 2/3     | Fixing file limit      |
    And the telemetry updates dynamically without page reloads.

  Scenario: Real-Time Alerts for Stalled Tasks Requiring Human Rescue
    Given an autonomous worker has exhausted its maximum attempts (3/3) and stalled
    When the lead views the Lead Console
    Then an urgent rescue banner appears highlighting "TASK-0014 Stalled: Awaiting Human Takeover"
    And clicking "Inspect Worktree" displays the agent's failure log and ".task-prompt.md" feedback.

  Scenario: One-Click Rescue Launch
    Given a stalled task displayed in the rescue panel of the Lead Console
    When the lead clicks "Takeover Task"
    Then the console copies the exact command "spec-ops rescue inspect TASK-0014" to the clipboard
    And provides a deep link directly to the task specification and failure diff.
