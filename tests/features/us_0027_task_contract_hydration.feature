Feature: Machine-Readable Task Contract and Architectural Context Hydration
  As an autonomous coding agent
  I want SpecOps to automatically compile an unambiguous task contract into .task-prompt.md
  So that I understand all architectural constraints and acceptance criteria immediately upon entering a worktree

  Scenario: Hydrating Task Contract into Worktree Environment
    Given a refined backlog task "TASK-0012" with target bounded context "core"
    And the task cites governing ADRs "ADR-0002, ADR-0003" and acceptance criteria from "US-0002"
    When the worker engine initializes the worktree for "TASK-0012"
    Then a ".task-prompt.md" file is generated at the worktree root
    And the prompt explicitly specifies the 500-line file length limit invariant
    And the prompt specifies blackbox frontdoor verification rules with zero private mocks
    And the prompt injects the exact preflight command chain "uv lock --check && uv run pytest && uv run spec-ops health"
    And the prompt instructs the agent that "docs/project/backlog/" must not be modified on feature branches.
