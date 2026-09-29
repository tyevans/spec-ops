Feature: Diataxis Documentation Drift Auditor and Validator
  As an engineering lead or system architect
  I want an automated documentation audit command "spec-ops docs audit"
  So that Diataxis quadrants, CLI reference specs, and markdown code snippets remain 100% synchronized with code.

  Scenario: Auditing compliant Diataxis documentation
    Given a project initialized with SpecOps and Diataxis documentation
    When the developer executes "spec-ops docs audit"
    Then the audit command exits with code 0
    And reports that all 5 approved quadrants are verified
    And reports status CLEAN with 0 errors

  Scenario: Auditing documentation with unapproved quadrant files
    Given a project initialized with SpecOps and Diataxis documentation
    And an unapproved documentation file is added to "docs/misc/random.md"
    When the developer executes "spec-ops docs audit"
    Then the audit command exits with code 1
    And reports status DRIFT DETECTED
    And identifies the unapproved quadrant "misc"
