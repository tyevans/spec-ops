Feature: Remote CI Failure Diagnostic Ingestion and In-Worktree Repair Loop

  Scenario: Ingesting Failed GitHub Actions Log for Autonomous CI Repair
    Given an open pull request for branch "task/TASK-0020" created by Morgan
    When remote GitHub Actions checks fail on the pull request
    And the agent executes "spec-ops worker ci-heal --task TASK-0020"
    Then SpecOps executes "gh run view --log-failed" to extract the failed step logs
    And extracts the relevant failure trace into ".task-prompt.md"
    And opens the existing worktree ".worktrees/task-0020"
    And invokes Morgan with the failure context to apply a targeted fix
    When Morgan fixes the failure and local preflight passes
    Then the worker pushes the updated branch to GitHub and re-triggers remote CI.
