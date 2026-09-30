Feature: Fast Incremental In-Worktree Preflight Runner with Targeted Step Isolation

  Scenario: Running isolated failed step with cached preflight results
    Given a rescued worktree ".worktrees/task-0010" where "uv lock --check" and "spec-ops health" previously passed
    And only the unit test suite "uv run pytest tests/test_visualizer.py" failed
    When the engineer is inside ".worktrees/task-0010" and executes "spec-ops rescue test --only-failed"
    Then only "uv run pytest tests/test_visualizer.py" is re-executed
    And previously passed invariant checks and lockfile validations are skipped
    And the check completes in under 3 seconds.

  Scenario: Rapid feedback cycle during local rescue iteration
    Given the engineer edits a file inside the rescued worktree
    When the engineer runs "spec-ops rescue test --step lint"
    Then only the linting and formatting check ("ruff check && ruff format --check") runs
    And the terminal displays immediate pass/fail status without running integration tests.

  Scenario: Enforcing mandatory full-suite revalidation upon rescue completion
    Given the engineer has iterated using targeted step checks
    When the engineer runs "spec-ops rescue TASK-0010 --complete"
    Then the rescue manager bypasses all caches and executes the complete, un-truncated preflight pipeline:
      | Step 1 | uv lock --check         |
      | Step 2 | spec-ops health         |
      | Step 3 | ruff check              |
      | Step 4 | full pytest test suite  |
    And integration into "main" proceeds only when all preflight stages pass unconditionally.
