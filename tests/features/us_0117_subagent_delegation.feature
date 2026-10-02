@us-0117 @TASK-0187 @orchestrator @subagent
Feature: Multi-Agent SDLC Subagent Delegation and Spec Consultation (US-0117)
  As an AI-native engineering lead and autonomous SDLC orchestrator
  I want subagents to consult approved specifications in "docs/project/" and coordinate with peer subagents
  So that lifecycle phases remain aligned with personas, PRDs, user stories, ADRs, and bounded contexts without drift.

  Scenario: Multi-Agent SDLC Subagent Delegation and Spec Consultation
    Given an orchestrator agent coordinating a project lifecycle
    When the orchestrator delegates tasks across SDLC phases (personas, stories, PRD, tasks, implementation)
    Then specialized subagents consult existing approved specs in "docs/project/" to guide implementation
    And report execution state back to the lead orchestrator.

  Scenario: Subagent peer consultation detects cross-boundary seam violations
    Given an implementation subagent working in an isolated worktree
    When the subagent requests peer consultation for proposed cross-context modifications
    Then the peer review evaluates the request against active ADRs and bounded contexts
    And returns actionable feedback and approval state before commit staging.

  Scenario: Subagent specification validation requires living specs in docs/project
    Given an implementation subagent with missing or unapproved specifications
    When peer consultation evaluates the subagent request
    Then missing specification errors are flagged
    And the consultation guidance requires anchoring changes to accepted living specs.
