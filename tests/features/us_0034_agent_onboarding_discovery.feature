@us_0034 @onboarding @agents_md
Feature: Autonomous Agent Onboarding and Capability Discovery via AGENTS.md

  Scenario: Agent Constitution Ingestion and Command Discovery
    Given a freshly cloned repository governed by SpecOps
    When an autonomous agent inspects "AGENTS.md" at the repository root
    Then the agent discovers the 8 Hard Invariants including <500 line limits and blackbox testing
    And the agent discovers the mandatory Diataxis documentation integrity requirements
    And when the agent runs "spec-ops profiles info --json"
    Then the CLI returns active architectural profile rules and quality preflight commands in JSON
    And the agent confirms all verification requirements before generating any code.
