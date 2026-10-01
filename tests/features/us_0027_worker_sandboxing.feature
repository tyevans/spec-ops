Feature: Zero-Trust Autonomous Worker Process Sandboxing and Environment Scrubbing

  Scenario: Scrubbing sensitive environment variables before worker spawn
    Given an ambient parent environment containing "AWS_SECRET_ACCESS_KEY" and "GITHUB_TOKEN"
    When the worker sandbox sanitizes the execution environment
    Then the resulting worker environment dictionary contains only allowlisted variables
    And all high-entropy secret variables are stripped

  Scenario: Blocking non-allowlisted command execution in sandboxed worktree
    Given a sandboxed worker runner
    When an attempt is made to execute an unapproved binary outside the allowlist
    Then the execution is rejected with a security violation error
    And zero subprocesses are spawned
