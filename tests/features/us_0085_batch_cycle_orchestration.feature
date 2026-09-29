Feature: Autonomous Batch Cycle Orchestration with Dynamic Task Unblocking

  Scenario: Dynamic Downstream Task Unblocking within a Single Cycle Run
    Given task "TASK-0030" is refined and unblocked in the priority queue
    And task "TASK-0031" depends on "TASK-0030" and is currently blocked
    When the user runs "spec-ops cycle --max-tasks 2"
    Then the cycle orchestrator executes "TASK-0030" in an isolated worktree and merges it into "main"
    And immediately re-evaluates the backlog queue to find that "TASK-0031" dependencies are now satisfied
    And pulls "TASK-0031" into active execution as the second task of the cycle
    And generates a cycle completion summary showing 2 tasks executed and 0 failures.

  Scenario: Graceful Cycle Interruption on SIGINT Signal
    Given an active autonomous cycle running task "TASK-0032"
    When the operator sends an interrupt signal (SIGINT / Ctrl+C) to the cycle process
    Then the cycle orchestrator traps the signal and initiates graceful shutdown
    And allows the current worktree operation to reach a safe checkpoint without killing git mid-write
    And ensures "MERGE_LOCK" is released and no orphaned lockfiles remain on disk
    And outputs a cycle report summarizing completed tasks and the preserved state of the interrupted task.
