@us_0012 @profiles
Feature: Custom Architectural Profile Authoring and Multi-Repo Distribution
  As an agentic systems architect,
  I want to author, validate, and export custom architectural profile packages containing organization-specific ADRs, configuration presets, and agent constitution templates,
  So that all distributed microservices and autonomous agents across the engineering organization adhere to unified architectural standards and quality invariants.

  Scenario: Packaging a custom organizational profile
    Given a local profile definition directory "profiles/fintech-service" containing custom ADRs and "profile.toml"
    When the architect runs "spec-ops profiles package profiles/fintech-service --out dist/fintech-service.sop"
    Then a verified profile bundle "dist/fintech-service.sop" is created
    And the bundle contains validated ADR frontmatter, custom file limits, and agent rule fragments.

  Scenario: Initializing a project using an exported custom profile bundle
    Given a blank repository directory
    And a custom profile bundle "fintech-service.sop"
    When the architect runs "spec-ops init --profile dist/fintech-service.sop"
    Then the custom organization ADRs are installed in "docs/project/adrs/accepted/"
    And the generated "AGENTS.md" incorporates the custom profile's specific compliance invariants
    And "specops.toml" records the installed profile identifier and version.

  Scenario: Detecting conflicting or duplicate ADR numbers in composite profiles
    Given an architect attempts to initialize a project with profiles "core" and an invalid custom profile reusing "ADR-0001"
    When the architect runs "spec-ops init --profile core,./invalid-profile"
    Then the command exits with code 1
    And displays "Profile Error: Conflict detected for ADR-0001 between 'core' and 'invalid-profile'".
