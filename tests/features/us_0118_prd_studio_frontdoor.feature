Feature: US-0118 PRD Studio Blackbox Frontdoor Verification
  As Taylor the Product Manager & Technical Writer
  I want to run `spec-ops prd studio --open` and author PRDs via the local web interface
  So that PRD specifications can be drafted, validated, and persisted without manual terminal commands.

  Scenario: Launching PRD Studio web server through frontdoor runner
    Given a project initialized with SpecOps
    When the user launches the PRD Studio server on a local test port
    Then the server responds to HTTP requests at "/studio" with the studio interface
    And the server provides REST API access to "/api/studio/state".

  Scenario: End-to-end authoring and persistence via frontdoor HTTP endpoints
    Given a running PRD Studio web server
    When the user creates a new draft for persona "Taylor" titled "UAT Release Receipt Signoff"
    And adds checkable outcome "Running spec-ops prd uat generates verifiable receipt"
    And submits a request to save the draft
    Then the PRD file is persisted under docs/project/product/idea/
    And the saved document satisfies ADR-0001 specification invariants.
