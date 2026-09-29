Feature: Product Discovery Guide and Falsifiable PRD Markdown Linter
  As a product manager
  I want an interactive PRD discovery guide and an automated quality linter to validate PMaC documents against structural and falsifiability heuristics
  So that I can author high-clarity PRDs with unambiguous problem statements, explicit anti-goals, and falsifiable checkable outcomes without needing deep git or CLI expertise.

  Scenario: Interactively guiding an author through PRD discovery scaffolding
    When Taylor executes "spec-ops prd new"
    Then the CLI initiates an interactive discovery questionnaire prompting for:
      | question                                                            |
      | Target Persona (selected from docs/project/user_stories/PERSONAS.md) |
      | What the person cannot do today (customer friction statement)       |
      | What good looks like (core capabilities)                            |
      | What this does not do (scope boundaries and non-goals)              |
      | Checkable Outcomes (at least one observable verification criterion) |
    And upon completion scaffolds a clean Markdown PRD under "docs/project/product/idea/" with valid YAML frontmatter.

  Scenario: Catching missing or incomplete sections during PRD markdown linting
    Given a draft PRD "docs/project/product/idea/prd-0005-billing.md" that omits the "## What this does not do" section
    When Taylor executes "spec-ops prd lint docs/project/product/idea/prd-0005-billing.md"
    Then the linter reports violation: "Missing required section: '## What this does not do'"
    And reports guidance: "Define explicit anti-goals to prevent multi-agent scope creep"
    And exits with code 1.

  Scenario: Linting checkable outcomes for non-falsifiable language
    Given a draft PRD containing checkable outcomes:
      | outcome                                                      |
      | Outcome 1: The UI looks clean and modern                     |
      | Outcome 2: Running 'spec-ops billing invoice' returns code 0 |
    When Taylor executes "spec-ops prd lint" on the draft PRD
    Then the linter flags Outcome 1: "Subjective adjective 'clean and modern' is unfalsifiable"
    And passes Outcome 2 as a valid falsifiable frontdoor contract
    And returns a passing grade only when all outcomes are verifiable.
