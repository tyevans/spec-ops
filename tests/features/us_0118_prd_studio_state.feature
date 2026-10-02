Feature: US-0118 PRD Studio Domain Model and State Handlers
  As Taylor the Product Manager & Technical Writer
  I want a reactive state manager and domain models for authoring and validating PRDs
  So that PRD drafts can be manipulated, validated, persisted, and stage-promoted without terminal interaction.

  Scenario: Initializing a new PRD draft with reactive validation
    Given a fresh PRD Studio session
    When the user creates a new draft for persona "Taylor" titled "Self-Service Notification Center"
    And adds a checkable outcome "Running spec-ops prd studio launches the UI"
    Then the session state is marked as dirty
    And the draft validation passes without schema violations.

  Scenario: Loading an existing PRD specification into editor buffer
    Given a repository initialized with accepted and idea PRDs
    When the user loads PRD "PRD-0003" into the studio state manager
    Then the active PRD ID is set to "PRD-0003"
    And the checkable outcomes and problem statement are populated
    And the session state is marked as not dirty.

  Scenario: Reordering and removing checkable outcomes
    Given a PRD draft with 3 checkable outcomes
    When the user reorders the outcomes in reverse order
    Then the outcomes array reflects the new sequence
    And when the user removes the first outcome
    Then 2 checkable outcomes remain in the draft.

  Scenario: Saving draft and promoting PRD lifecycle stage
    Given an idea PRD draft with valid fields and checkable outcomes
    When the studio state manager saves the draft to disk
    Then a markdown file is created under docs/project/product/idea/
    And when the PRD is promoted to stage "shaped"
    Then the PRD file moves to the shaped directory and state reflects the new stage.
