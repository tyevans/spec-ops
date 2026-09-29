Feature: Project Initialization with Architectural Profiles
  As an agentic software architect
  I want to initialize a new codebase with spec-ops init
  So that my repository immediately adopts version-controlled project management, baseline ADR guardrails, and quality invariants.

  Scenario: Bootstrapping a New Repository
    Given a blank project directory
    When the engineer executes "spec-ops init --name TestApp --profile core,bdd,ddd"
    Then the directory structure "docs/project/" is created with adrs, product, user_stories, and backlog
    And 7 baseline ADRs are installed into "docs/project/adrs/accepted/"
    And "specops.toml" is generated with matching project settings
