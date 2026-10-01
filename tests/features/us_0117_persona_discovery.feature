Feature: Autonomous Persona Discovery and Living Maintenance Engine
  As an agentic systems architect and engineering lead
  I want autonomous persona discovery and coverage auditing
  So that personas stay continuously synchronized with evolving PRDs, stories, and git commits.

  Scenario: Autonomous Persona Discovery and Coverage Audit
    Given a repository with evolving bounded contexts and newly introduced architectural roles
    When the orchestrator executes "spec-ops persona audit"
    Then the engine inspects all accepted PRDs, stories, and git commits
    And highlights uncovered archetypes with recommended profile drafts for "PERSONAS.md".

  Scenario: Synchronizing Synthesized Persona Profiles for Emerging Archetypes
    Given uncovered emerging archetypes detected in repository specifications
    When the orchestrator executes "spec-ops persona sync --apply"
    Then synthesized persona profile additions are written to "docs/project/user_stories/PERSONAS.md"
    And subsequent persona audits confirm zero unrepresented archetypes.
