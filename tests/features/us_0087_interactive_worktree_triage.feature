Feature: Interactive Preserved Worktree Triage and Failure Diagnostic Breakdown

  Scenario: Categorizing preflight failure modes in a stalled worktree
    Given an autonomous worker session for "TASK-0012" has exhausted its 3 self-healing attempts
    And the worktree ".worktrees/task-0012" is preserved on branch "feat/TASK-0012"
    When the engineer executes "spec-ops rescue triage TASK-0012"
    Then the CLI displays a categorized diagnostic summary:
      | Category               | Status | Details                                                     |
      | File Length Invariant  | FAIL   | src/spec_ops/core/parser.py (514 lines > 500 limit)         |
      | Test Suite             | FAIL   | tests/test_parser.py::test_parse_syntax (AssertionError)   |
      | Lockfile Integrity     | PASS   | uv.lock synchronized                                        |
      | Working Tree State     | DIRTY  | 3 modified files, 1 untracked file                          |
    And the CLI presents an interactive triage menu with options: "[d]iff, [p]atch, [s]hell, [r]eset, [c]omplete, [q]uit".

  Scenario: Inspecting AST and line count diffs per modified file
    Given the engineer is in the interactive triage menu for "TASK-0012"
    When the engineer selects "[d]iff" and chooses "src/spec_ops/core/parser.py"
    Then the CLI renders a syntax-highlighted diff comparing the worktree file against "HEAD"
    And displays the net line delta (+42 lines) and headroom to the 500-line invariant limit (-14 lines headroom, VIOLATION).

  Scenario: Navigating directly to recommended rescue actions
    Given the failure breakdown indicates only file-length invariant violations with all tests passing
    When the triage analysis completes
    Then the CLI outputs a targeted recommendation:
      """
      Recommendation: Code passes tests but violates file limits. Run 'spec-ops rescue shell TASK-0012' to decompose parser.py, then 'spec-ops rescue TASK-0012 --complete'.
      """
