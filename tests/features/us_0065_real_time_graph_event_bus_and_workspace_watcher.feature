Feature: Real-Time In-Memory Graph Event Bus and Workspace Change Watcher
  As an autonomous coding agent,
  I want spec-ops graph watch to provide an in-memory, event-driven graph synchronization loop reacting to filesystem events,
  So that active worktrees maintain real-time relational graph consistency and immediately surface broken references or invariant breaches as task files and specifications are authored.

  Scenario: Publishing real-time graph delta events when a task transitions status
    Given the background daemon "spec-ops graph watch --event-stream" is running in a worktree
    When Morgan moves "docs/project/backlog/proposed/0010-feature.md" to "docs/project/backlog/refined/0010-feature.md"
    Then the watcher detects the filesystem move event within 50 milliseconds
    And updates the in-memory graph node "TASK-0010" status to "Refined"
    And emits a structured event:
      """
      {"event": "node_updated", "id": "TASK-0010", "type": "task", "status": "Refined", "edges_recalculated": 3}
      """

  Scenario: Immediate warning emission upon authoring an unanchored reference
    Given the watcher "spec-ops graph watch" is actively running
    When Morgan writes a new story referencing "governing_prd: PRD-9999"
    And "PRD-9999" does not exist in "docs/project/product/"
    Then the watcher immediately outputs a real-time warning to the stream:
      """
      warning: Broken Reference Created in docs/project/user_stories/accepted/us-0060.md
      -> References non-existent PRD: PRD-9999
      """
    And flags the in-memory node as "DRAFT_INVALID" until resolved.

  Scenario: Clean shutdown and debounced multi-file git checkout handling
    Given the watcher is running on a repository branch
    When Morgan runs "git checkout -b task/TASK-0042" causing 15 files to update simultaneously
    Then the watcher debounces filesystem events across a 100ms window
    And executes a single batched graph recalculation
    And emits a summary: "Batched update: 15 files synchronized in 42ms".
