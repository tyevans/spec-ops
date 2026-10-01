Feature: Multi-Faceted BDD User Story Generation and Cross-Cutting Traceability
  As an agentic systems architect and engineering lead
  I want multi-faceted user story authoring and bidirectional traceability
  So that stories are explicitly categorized across personas, bounded contexts, and vertical slices with verified frontdoors.

  Scenario: Multi-Faceted BDD Story Generation
    Given an accepted PRD with defined checkable outcomes
    When the orchestrator executes "spec-ops story create --prd PRD-0006 --persona Jordan --bc worker"
    Then a new user story is scaffolded in "docs/project/user_stories/accepted/"
    And executable Gherkin scenarios are generated without private mock backdoors
    And "docs/project/user_stories/REGISTRY.md" is updated atomically.

  Scenario: Cross-Cutting Traceability Audit
    Given a project repository with PRDs, user stories, personas, and backlog tasks
    When the orchestrator executes "spec-ops story trace"
    Then unbroken bidirectional lineage is reported across Personas, PRDs, Stories, Tasks, and Commits
    And broken references or orphaned items are flagged.
