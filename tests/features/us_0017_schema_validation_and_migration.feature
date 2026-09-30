@us_0017
Feature: US-0017 Specification Frontmatter Schema Validation and Automated In-Place Migration

  Scenario: Validating specification frontmatter against current schema
    Given specification documents in "docs/project/" containing valid YAML frontmatter matching current models
    When the architect runs "spec-ops schema check"
    Then the command exits with code 0
    And reports "Schema Check Passed: All specification documents conform to schema v2.0".

  Scenario: Performing dry-run migration to inspect schema updates
    Given an older task document using legacy field "governing_adr: 0001" instead of "governing_adrs: ['ADR-0001']"
    When the architect runs "spec-ops schema migrate --dry-run"
    Then the command outputs a unified diff showing projected frontmatter transformations
    And leaves files on disk unmodified.

  Scenario: Executing in-place frontmatter migration preserving Markdown body contents
    Given an older task document with legacy frontmatter fields and a 100-line Markdown technical specification
    When the architect runs "spec-ops schema migrate --in-place"
    Then the YAML frontmatter is rewritten to the new schema format
    And the exact Markdown body, headings, and code blocks below the frontmatter are preserved byte-for-byte.
