Feature: Default SpecOps SDLC Orchestrator Skill Scaffolding on Project Onboarding (US-0132)

  Scenario: Scaffolding the SpecOps SDLC orchestrator skill by default on spec-ops init
    Given a blank project directory
    When the user runs "spec-ops init --name TestApp" without specifying agent flags
    Then ".agents/skills/spec-ops/SKILL.md" is scaffolded into the repository
    And "specops.toml" is created.

  Scenario: Scaffolding supporting reference runbooks and primers during onboarding
    Given a blank project directory
    When the user initializes a project via "spec-ops init"
    Then ".agents/skills/spec-ops/references/cli_primer.md" exists
    And ".agents/skills/spec-ops/references/balancing_loop.md" exists
    And ".agents/skills/spec-ops/references/orchestration_protocol.md" exists.

  Scenario: Scaffolding the orchestrator skill during brownfield adoption
    Given an existing codebase directory
    When the user executes "spec-ops adopt"
    Then ".agents/skills/spec-ops/SKILL.md" is created alongside PMaC governance documents.
