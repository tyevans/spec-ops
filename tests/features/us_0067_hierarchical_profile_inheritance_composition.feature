@us_0067 @profiles
Feature: Hierarchical Profile Inheritance, Composition, and Invariant Overrides
  As an agentic systems architect,
  I want to define composite architectural profiles that inherit from parent profiles and override specific invariant thresholds, vertical slice definitions, and quality gates,
  So that platform teams can standardize enterprise-wide architectural foundations while tailoring specific domain constraints across microservices and bounded contexts.

  Scenario: Defining a custom profile inheriting from parent profiles
    Given a profile definition file "profiles/enterprise-fintech/profile.toml"
    And the profile specifies "extends = ['core', 'security', 'ddd']"
    And defines custom vertical slices for audit trails and regulatory compliance
    When the architect runs "spec-ops profiles validate profiles/enterprise-fintech"
    Then the profile dependency tree resolves without circular dependencies
    And aggregates all inherited baseline ADRs sequentially without slug collisions.

  Scenario: Overriding specific invariant thresholds in a derived profile
    Given an inherited profile "enterprise-fintech" extending "core"
    And "profile.toml" configures "[overrides.architecture] file_length_limit = 350" and "[overrides.quality] require_mutation_testing = true"
    When a project is initialized with "spec-ops init --profile ./profiles/enterprise-fintech"
    Then "specops.toml" is generated with "file_length_limit = 350"
    And "AGENTS.md" reflects the strict 350-line limit in its Hard Invariants section
    And the generated ADR registry incorporates both base and enterprise-specific ADRs.

  Scenario: Detecting circular inheritance and conflicting invariant overrides
    Given profile "profile-a" extending "profile-b" and "profile-b" extending "profile-a"
    When the architect runs "spec-ops profiles validate profiles/profile-a"
    Then the validation fails with exit code 1
    And displays "Profile Inheritance Error: Circular dependency detected (profile-a -> profile-b -> profile-a)".
