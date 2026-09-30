Feature: In-Worktree Pre-Flight Verification and Iterative Self-Healing Feedback Loop

  Scenario: Autonomous Self-Healing on Preflight Health Check Violation
    Given an isolated worktree executing task "TASK-0014"
    When the agent implements code where a source file contains 520 lines
    And the worker engine executes the preflight suite "uv run spec-ops health"
    Then the preflight check fails reporting a file length violation on line 520
    And the worker engine appends the exact error log and file location to the agent feedback prompt
    And re-invokes the agent in the worktree for repair attempt 2
    When the agent decomposes the module into two files under 400 lines each
    And preflight re-runs cleanly
    Then the worker marks preflight as passed and proceeds to staging.

  Scenario: Graceful Worktree Preservation on Exhausted Self-Healing Retries
    Given an isolated worktree executing task "TASK-0014"
    When the agent fails preflight verification across all configured maximum attempts (3 attempts)
    Then the worker halts without creating a broken git commit
    And preserves the worktree at ".worktrees/task-0014" with diagnostic failure logs
    And outputs a human takeover command "spec-ops rescue TASK-0014".
