@us_0042
Feature: US-0042: One-Command Developer Environment Doctor and Workspace Onboarding
  As a new or returning human software engineer setting up a SpecOps-governed repository
  I want to execute spec-ops doctor to audit and auto-repair my local development environment
  So that I can achieve a green, fully compliant local development setup in under 60 seconds with zero onboarding guesswork.

  Scenario: Diagnostic audit of local developer tooling and workspace health
    Given an engineer has cloned a SpecOps repository
    When the engineer executes "spec-ops doctor"
    Then the command verifies:
      | Component           | Check                                                   | Status  |
      | UV Package Manager  | UV installed and lockfile synchronized (uv lock --check) | PASS    |
      | Git Worktree Setup  | .worktrees/ directory configured in .gitignore          | PASS    |
      | Pre-Commit Hooks    | Git pre-commit hook active with spec-ops health check   | FAIL    |
      | Line Limit Health   | Zero source files exceed configured limit (<500 lines)   | PASS    |
    And the CLI indicates that 1 issue requires resolution.

  Scenario: Automated repair of missing hooks and configuration
    Given the pre-commit hook is uninstalled
    When the engineer executes "spec-ops doctor --fix"
    Then the command installs the git pre-commit hook
    And verifies the complete toolchain
    And outputs "Development environment is healthy and ready for active engineering.".
