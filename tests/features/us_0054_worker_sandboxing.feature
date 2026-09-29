Feature: Autonomous Worker Process Sandboxing and Shell Command Allowlisting

  Scenario: Intercepting and terminating forbidden shell commands
    Given "specops.toml" configures "[execution.sandbox]" with allowed_commands = ["uv", "git", "pytest", "ruff"]
    When an autonomous agent process attempts to invoke a forbidden utility like "curl", "wget", "sudo", or "rm -rf /"
    Then the process sandbox execution interceptor blocks the command
    And writes a security alert event to ".worktrees/<task-id>/.security-audit.log"
    And terminates the worker attempt with exit code 126 (Command Prohibited).

  Scenario: Network isolation during test verification
    Given "specops.toml" sets "[execution.sandbox] isolate_network = true"
    When the worker executes the test preflight suite
    Then network socket calls to non-loopback addresses are blocked
    And any test attempting unexpected external network egress fails cleanly as an architectural violation.
