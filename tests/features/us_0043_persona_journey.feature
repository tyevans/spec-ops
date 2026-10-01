Feature: Persona Customer Journey Map and Pain Point Matrix Visualizer
  As a product lead or architect
  I want to visualize customer journeys and audit pain point resolution coverage
  So that I can verify that PRD outcomes and user stories address core persona pain points

  Scenario: Auditing persona pain point resolution coverage
    Given a project repository with persona "Taylor" having 3 defined pain points
    When the product lead runs "spec-ops prd journey --persona Taylor"
    Then a journey coverage report is generated
    And identifies which pain points have linked accepted stories and which remain unaddressed

  Scenario: Exporting standalone HTML customer journey map
    Given an accepted PRD with mapped persona user stories
    When the user executes "spec-ops prd journey --format html"
    Then a standalone HTML journey map is produced
    And includes verifiable coverage metrics
