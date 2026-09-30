@us_0080 @worker @runners
Feature: Pluggable Agent Runner Templates and Worktree Dry-Run Simulation

  Scenario: Configuring Custom Agent Runner with Template Placeholders
    Given a SpecOps configuration defining "execution.agent_command" as "aider --message-file {prompt_file} --yes --auto-commits"
    And a refined task "TASK-0014" targeting bounded context "worker"
    When the worker engine prepares the execution environment for "TASK-0014"
    Then the worker interpolates "{prompt_file}" to the absolute path of ".worktrees/task-0014/.task-prompt.md"
    And sets environment variables "SPEC_OPS_WORKTREE" and "PWD" to the worktree directory
    And constructs the process argument list safely without shell quote mangling.

  Scenario: Zero-Cost Worktree Dry-Run Simulation
    Given a refined task "TASK-0010" in "docs/project/backlog/refined/"
    When the user runs "spec-ops worker --task TASK-0010 --dry-run"
    Then an isolated worktree is created at ".worktrees/task-0010" on branch "feat/task-0010"
    And the task prompt is generated at ".worktrees/task-0010/.task-prompt.md" containing governing ADRs, PRDs, and preflight commands
    And no external agent process is spawned
    And the worker cleans up the dry-run worktree and reports success without modifying git history on "main".
