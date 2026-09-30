Feature: US-0072 — Zero-Dependency Native Git Hook Scaffolding and Autonomous Worktree Guardrails

  Scenario: Scaffolding native git pre-commit and pre-push hooks
    Given a git repository initialized with SpecOps
    When the security officer runs "spec-ops scaffold hooks --native"
    Then executable shell scripts are installed directly into ".git/hooks/pre-commit" and ".git/hooks/pre-push"
    And the pre-commit hook runs "uv run spec-ops health" verifying file length limits (<500 lines) and staged file invariants
    And does not require third-party python pre-commit tooling.

  Scenario: Enforcing strict backlog isolation on feature branches via hook
    Given a developer or agent working on feature branch "feat/TASK-0012"
    When the worker attempts to stage and commit modifications to "docs/project/backlog/PRIORITY.md"
    Then the native pre-commit hook intercepts the commit
    And aborts with exit code 1
    And displays "Invariant Violation (ADR-0005): Feature branches are strictly forbidden from modifying docs/project/backlog/. Backlog transitions are managed automatically upon merge to main."

  Scenario: Propagating hooks automatically to autonomous worker worktrees
    Given an autonomous task execution dispatched via "spec-ops worker --task TASK-0020"
    When the worker engine provisions an isolated git worktree at ".worktrees/TASK-0020"
    Then the hook scaffolder ensures ".git/worktrees/TASK-0020/hooks" or shared git hooks remain active in the worktree
    And blocks the autonomous agent from committing backdoor mocks or invalid lockfiles before creating a pull request.
