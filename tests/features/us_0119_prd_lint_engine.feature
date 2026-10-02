Feature: US-0119 PRD Linter Line-Level Remediation Engine
  As Alex the Agentic Systems Architect and Jordan the Engineering Lead
  I want `spec-ops prd lint` to generate line-level suggestions and remediation hints
  So that unfalsifiable language, missing personas, and structural defects can be remediated before stage promotion.

  Scenario: Detecting unmapped persona with line-level assignment suggestion
    Given a PRD document with missing target persona frontmatter
    When the PRD lint engine analyzes the document
    Then a diagnostic with rule "PRD-LINT-001" is reported
    And a line-level suggestion provides an authorized persona replacement.

  Scenario: Flagging unfalsifiable outcomes with measurable rewrite suggestions
    Given a PRD document containing subjective outcome "The user interface is fast and modern"
    When the PRD lint engine analyzes the document
    Then a diagnostic with rule "PRD-LINT-002" is reported on that line
    And the suggested text replaces the subjective terms with measurable behavioral contracts.

  Scenario: Validating a compliant PRD document
    Given a PRD document with valid frontmatter, persona, problem statement, and checkable outcomes
    When the PRD lint engine analyzes the document
    Then the report marks the document as valid with zero error diagnostics.
