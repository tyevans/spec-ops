Feature: Automated Backlog Protection and Accidental Modification Guardrails
  As an autonomous coding agent
  I want SpecOps to automatically detect and revert accidental modifications to shared project management files within my feature worktree
  So that my commits strictly contain functional code and tests

  Scenario: Intercepting and Reverting Accidental Backlog Changes
    Given an isolated worktree on branch "task/TASK-0015"
    When the agent implements feature code in "src/spec_ops/backlog/"
    And the agent inadvertently modifies "docs/project/backlog/PRIORITY.md" and "docs/project/backlog/refined/task-0015.md"
    When the worker engine initiates commit preparation
    Then the worker detects modifications inside "docs/project/backlog/"
    And automatically executes a git checkout HEAD on "docs/project/backlog/" to discard the changes
    And stages only legitimate source code and test files in "src/" and "tests/"
    And creates a commit containing zero modifications to shared backlog indices.
