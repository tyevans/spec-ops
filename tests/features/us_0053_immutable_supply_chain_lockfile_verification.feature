@security @us_0053
Feature: Immutable Supply-Chain Lockfile Verification and Slopsquatting Defense

  Scenario: Rejecting unauthorized dependency additions in task worktrees
    Given a backlog task whose frontmatter does not declare "allows_dependencies: true"
    When an autonomous coding agent modifies "pyproject.toml" or "uv.lock" to add an unapproved package
    Then "spec-ops worker" preflight detects the unauthorized lockfile alteration
    And the worker halts execution with an "Unauthorized Dependency Modification" violation
    And the task is flagged for human triage and not merged into "main".

  Scenario: Cryptographic hash verification for authorized dependency tasks
    Given a backlog task with "allows_dependencies: true" explicitly approved in frontmatter
    When the worker updates dependencies
    Then "uv lock --check" executes to verify all package hashes match upstream cryptographic hashes
    And any untrusted or unpinned package causes preflight to fail with returncode 1.
