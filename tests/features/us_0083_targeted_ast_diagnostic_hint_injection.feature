Feature: Targeted AST Diagnostic Hint Injection and Empty-Diff Guardrails in Self-Healing Loops

  Scenario: Targeted AST Diagnostic Injection for File Length Overruns
    Given an isolated worktree executing "TASK-0005"
    When the agent produces "src/spec_ops/backlog/engine.py" containing 540 lines exceeding the 500-line limit
    And preflight detects the file length violation
    Then the worker engine parses the AST of "engine.py" to identify candidate function and class split seams
    And appends a structured diagnostic section to ".task-prompt.md":
    """
    ## AST Decomposition Hints (Attempt 1)
    - File: src/spec_ops/backlog/engine.py (540 lines, limit: 500)
    - Largest AST node: class TaskExecutionCoordinator (lines 120-410, 291 lines)
    - Suggested seam: extract TaskExecutionCoordinator into separate module
    """
    And re-invokes the agent with targeted refactoring guidance.

  Scenario: Guarding Against Empty or Whitespace-Only Agent Diffs
    Given an isolated worktree executing "TASK-0012" on attempt 1
    When the agent process exits with return code 0 but git status shows no tracked file modifications
    Then the worker engine flags the attempt as "No Modifications Produced"
    And injects feedback into the prompt warning the agent that implementation code is required
    And decrements remaining retry attempts without proceeding to preflight or merge.
