Feature: AST Self-Healing Diagnostic Injector for In-Worktree Preflight Recovery

  Scenario: Mapping preflight failure trace to target AST node
    Given a preflight failure output reporting an AssertionError at line 42 of a source file
    When the diagnostic injector processes the failure log
    Then the failing function AST node is identified
    And a structured diagnostic card includes the node signature and source context

  Scenario: Injecting actionable fix hints into worker retry prompt
    Given a worktree preflight failure violating file length limit ADR-0002
    When the diagnostic injector synthesizes retry guidance
    Then the retry prompt highlights the exact oversized module
    And provides decomposition guidance without modifying source files directly
