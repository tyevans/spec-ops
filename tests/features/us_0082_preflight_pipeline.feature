Feature: Multi-Stage Extensible Preflight Validation Pipeline with Early Fast-Fail

  Scenario: Fast-Fail on Early Security and Lockfile Verification Stage
    Given a worker executing "TASK-0019" in an isolated worktree
    And the preflight configuration defines sequential stages: "lockfile", "health", and "tests"
    When an agent updates "pyproject.toml" but fails to update "uv.lock"
    And the worker runs the preflight pipeline
    Then stage "lockfile" executes "uv lock --check" and fails with an out-of-sync error
    And the preflight pipeline immediately halts without executing subsequent "health" or "tests" stages
    And the failure output isolates the lockfile drift as the specific stage-1 failure.

  Scenario: Complete Pipeline Execution Across All Configured Gates
    Given an isolated worktree with valid lockfiles and clean file limits
    When the worker executes the full preflight pipeline
    Then the worker executes:
      | Stage     | Command                  | Required |
      | lockfile  | uv lock --check          | true     |
      | health    | uv run spec-ops health   | true     |
      | test      | uv run pytest            | true     |
    And each stage executes within its dedicated timeout limit
    And the worker logs a structured pipeline summary confirming all gates passed.
