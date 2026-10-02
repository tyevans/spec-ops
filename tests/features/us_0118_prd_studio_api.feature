Feature: US-0118 PRD Studio Public API Dispatch Contracts
  As Taylor the Product Manager & Technical Writer
  I want standardized HTTP API endpoints for PRD Studio session management
  So that the web client can inspect state, update fields, reorder outcomes, and persist PRD drafts via REST contracts.

  Scenario: Fetching studio session state and PRD registry via GET contracts
    Given an active PRD studio session connected to an initialized project
    When an HTTP GET request is dispatched to "/api/studio/state"
    Then the response status is 200 and returns the active session state
    When an HTTP GET request is dispatched to "/api/studio/prds"
    Then the response status is 200 and lists available PRDs.

  Scenario: Mutating draft fields and outcomes via POST contracts
    Given an active PRD studio session connected to an initialized project
    When an HTTP POST request is dispatched to "/api/studio/draft/update" with field "title" and value "Self-Service Notification Center"
    And an HTTP POST request is dispatched to "/api/studio/draft/update" with field "persona" and value "Taylor"
    And an HTTP POST request is dispatched to "/api/studio/draft/outcome/add" with outcome "Running spec-ops prd studio launches the UI"
    Then the response status is 200 and the draft is marked valid
    When an HTTP POST request is dispatched to "/api/studio/draft/save"
    Then the response status is 200 and the draft file path is returned.

  Scenario: Outcome reordering and removing via POST contracts
    Given a PRD draft populated with 3 checkable outcomes
    When an HTTP POST request is dispatched to "/api/studio/draft/outcome/reorder" with order [2, 1, 0]
    Then the response status is 200 and the outcomes are reversed
    When an HTTP POST request is dispatched to "/api/studio/draft/outcome/remove" with index 0
    Then the response status is 200 and 2 outcomes remain.
