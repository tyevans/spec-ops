@security @us_0111
Feature: Immutable Supply-Chain Lockfile Verification and Defense Gate

  Scenario: Rejecting unauthorized dependency additions in task worktrees
    Given a backlog task whose frontmatter does not declare "allows_dependencies: true"
    When an autonomous coding agent modifies "pyproject.toml" or "uv.lock" to add an unapproved package
    Then "spec-ops worker" preflight detects the unauthorized lockfile alteration
    And the worker halts execution with an "Unauthorized Dependency Modification" violation
    And the task is flagged for human triage and blocked from merging into "main".

  Scenario: Cryptographic hash verification for authorized dependency tasks
    Given a backlog task with "allows_dependencies: true" explicitly approved in its frontmatter
    When the worker updates dependencies and executes preflight verification
    Then "uv lock --check" executes to verify all package hashes match upstream cryptographic hashes
    And any untrusted, unpinned, or drifted package causes preflight to fail with returncode 1.

  Scenario: Integration gate verifies lockfile immutability across the branch diff
    Given an autonomous feature branch submitted for completion
    When the orchestrator executes "spec-ops queue complete <task-id>" under merge lock
    Then the engine verifies that the branch diff against "main" contains zero unstaged or unapproved lockfile alterations
    And passes only when lockfile integrity is cryptographically validated.
