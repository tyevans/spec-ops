@us_0089 @rescue
Feature: Safe Worktree Discard with Anti-Loop Failure Memory and Task Reset

  Scenario: Discarding worktree and capturing failure post-mortem into task frontmatter
    Given a stalled worktree ".worktrees/task-0024" where the agent attempted an invalid monkey-patching approach
    When the engineer executes:
      """
      spec-ops rescue reset TASK-0024 --reason "Agent attempted internal mock backdoors violating ADR-0003 instead of public CLI testing"
      """
    Then the git worktree ".worktrees/task-0024" and branch "feat/TASK-0024" are deleted
    And the task specification file "docs/project/backlog/refined/0024-*.md" is updated with frontmatter metadata:
      """
      failure_history:
        - attempt_date: 2026-09-29
          reason: "Agent attempted internal mock backdoors violating ADR-0003 instead of public CLI testing"
          failed_invariants: [ADR-0003]
      """
    And task "TASK-0024" remains in "docs/project/backlog/refined/" for re-assignment.

  Scenario: Automatic demotion to proposed stage when specification ambiguity is flagged
    Given an engineer determines that "TASK-0030" stalled because acceptance criteria were contradictory
    When the engineer executes "spec-ops rescue reset TASK-0030 --demote --reason 'Contradictory Gherkin criteria in Scenario 2'"
    Then the worktree and branch are cleaned up
    And the task file is moved from "docs/project/backlog/refined/" to "docs/project/backlog/proposed/"
    And "docs/project/backlog/PRIORITY.md" is synchronized without task "TASK-0030" blocking the refined queue.

  Scenario: Hydrating subsequent worker prompts with negative constraints from failure history
    Given task "TASK-0024" has recorded failure history citing "ADR-0003 violation"
    When an autonomous worker claims "TASK-0024" for a new attempt
    Then the generated ".task-prompt.md" includes a dedicated section:
      """
      ## Prior Attempt Failures & Anti-Patterns (DO NOT REPEAT)
      - Previous failure: Agent attempted internal mock backdoors violating ADR-0003 instead of public CLI testing.
      - Mandate: You must strictly use public frontdoor entrypoints with zero mock backdoors.
      """
