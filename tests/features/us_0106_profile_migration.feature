Feature: Architectural Profile Schema Migration and Version Evolvability
  As an agentic systems architect
  I want an automated profile migration engine
  So that legacy profile configurations can evolve non-destructively without manual YAML editing

  Scenario: Migrating legacy profile configuration to current schema
    Given a project configured with a legacy v1 profile.yaml
    When the developer runs spec-ops profile migrate
    Then the configuration is upgraded to the current schema version
    And all custom project rules and frontmatter settings are preserved intact

  Scenario: Checking profile version currency
    Given a project profile already synchronized with the current schema
    When the developer runs spec-ops profile migrate with check flag
    Then the command confirms profile is up to date
    And terminates with exit code 0
