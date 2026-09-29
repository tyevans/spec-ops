Feature: Autonomous Worker Process Sandboxing and Shell Command Execution Interceptors

  Scenario: Intercepting and terminating forbidden shell commands in worker worktrees
    Given "specops.toml" configures "[execution.sandbox]" with allowed_commands = ["uv", "git", "pytest", "ruff"]
    When an autonomous agent process attempts to invoke a forbidden utility like "curl", "wget", "sudo", or "rm -rf /"
    Then the process sandbox execution interceptor intercepts and aborts the subshell invocation
    And writes a structured security alert event to ".worktrees/<task-id>/.security-audit.log" with command string, parent PID, and timestamp
    And terminates the worker attempt with exit code 126 (Command Prohibited) and diagnostic error output.

  Scenario: Enforcing network isolation during preflight test execution
    Given "specops.toml" sets "[execution.sandbox] isolate_network = true"
    When the worker engine executes the test preflight verification suite in an isolated worktree
    Then all outbound TCP and UDP socket connections to non-loopback addresses are blocked by the network sandbox
    And any test attempting unexpected external network egress fails cleanly as an architectural boundary violation.

  Scenario: Seamless execution of allowlisted developer toolchain
    Given an autonomous worker executing within the hardened process sandbox
    When the worker executes allowlisted commands "uv run pytest" and "git status"
    Then the commands execute with zero latency degradation and standard stream redirection
    And stdout and stderr outputs are captured cleanly into the task execution log.
