Feature: Multi-Agent Platform Adapters (Claude, Cursor, Antigravity)
  As an agentic software architect
  I want spec-ops init to generate target agent rule sets and slash commands
  So that autonomous assistants (Claude Code, Cursor, Antigravity) immediately inherit repository invariants and PMaC workflows.

  Scenario: Generating Rules and Slash Commands for Target Agents
    Given a blank project directory
    When the engineer executes "spec-ops init --name PlatformApp --agent antigravity,claude,cursor"
    Then "CLAUDE.md" is generated for Claude Code
    And ".cursorrules" is generated for Cursor
    And "GEMINI.md" and slash command skills are generated for Antigravity
    And all generated files contain the hard invariant file limit under 500 lines
