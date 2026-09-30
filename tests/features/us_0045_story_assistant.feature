Feature: Low-Code Gherkin BDD Story Authoring and Frontdoor Step Assistant

  Scenario: Autocompleting Established Frontdoor Steps during Story Creation
    Given Taylor is authoring a new user story for "PRD-0001" in the visualizer Story Studio
    When Taylor types "Given " into the scenario editor
    Then the step assistant displays an autocomplete dropdown of registered frontdoor fixtures:
      | Step Pattern                                            | Domain Area |
      | Given a project initialized with SpecOps               | CLI / Setup |
      | Given the standalone visualizer is open in a browser    | Web / UI    |
      | Given an accepted PRD with linked user stories          | Backlog     |
    And selecting a step populates the scenario with valid Gherkin syntax.

  Scenario: Detecting and Flagging Private Backdoors (ADR-0003 Invariant)
    Given Taylor is authoring a Gherkin scenario
    When Taylor enters a step referencing private internals such as "Given the database table users has record 'admin'"
    Then the scenario assistant displays an architectural warning:
      """
      Backdoor violation (ADR-0003): Tests must exercise public frontdoors. Direct state manipulation is prohibited.
      """
    And suggests the compliant frontdoor alternative.
