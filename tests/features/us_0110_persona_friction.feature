Feature: Autonomous User Persona Journey Friction Auditor and Heuristic Evaluator

  Scenario: Auditing friction score for persona workflows
    Given established user personas and CLI command definitions
    When the developer runs spec-ops prd friction
    Then the engine computes friction indices across persona touchpoints
    And displays actionable recommendations for reducing operational ceremony

  Scenario: Flagging workflows exceeding friction threshold
    Given a workflow with high ceremony exceeding the configured friction threshold
    When spec-ops prd friction is evaluated with threshold check
    Then high-friction commands are flagged with remediation hints
