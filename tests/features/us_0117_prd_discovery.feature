Feature: Continuous Product Discovery and Living PRD Synthesis Workflow
  As an agentic systems architect and AI-native engineering lead
  I want an autonomous product discovery and PRD shaping workflow
  So that product ideas are systematically synthesized into accepted, falsifiable PRDs with verified checkable outcomes.

  Scenario: Autonomous PRD Discovery and Scaffolding
    Given an initialized SpecOps repository
    When the orchestrator executes 'spec-ops prd discover --title "Metric Collection" --persona "Alex (The Agentic Systems Architect)" --bc "metrics" --summary "Lack of telemetry" --non-interactive'
    Then a new PRD idea draft is scaffolded in "docs/project/product/idea/"
    And the PRD is registered in "docs/project/product/REGISTRY.md" with status "Idea"

  Scenario: Autonomous PRD Discovery and Lifecycle Advancement
    Given a raw idea in "docs/project/product/idea/"
    When the orchestrator executes 'spec-ops prd shape --id PRD-0001 --accept'
    Then the engine analyzes persona pain points and bounded context boundaries
    And prompts or generates checkable outcomes and non-goals
    And moves the PRD to "shaped/" or "accepted/" once lint checks pass
    And "docs/project/product/REGISTRY.md" reflects the updated status

  Scenario: Rejection of Unfalsifiable PRD Shaping
    Given a raw idea in "docs/project/product/idea/"
    When the orchestrator executes 'spec-ops prd shape --id PRD-0001 --outcomes "Clean and modern design, Fast response, Simple UI" --accept'
    Then the shaping gate blocks promotion
    And reports falsifiability violations for subjective adjectives
    And the PRD remains in its original lifecycle stage

  Scenario: Verifying public frontdoor contract satisfaction
    Given the system is initialized and ready
    When the user executes the workflow for "Continuous Product Discovery and Living PRD Synthesis Workflow"
    Then Autonomous PRD Discovery and Lifecycle Advancement*
    And observable outputs satisfy public contracts without backdoor tampering
