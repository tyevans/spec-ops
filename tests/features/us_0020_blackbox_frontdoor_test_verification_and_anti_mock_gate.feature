@us_0020 @quality @anti_mock
Feature: US-0020: Blackbox Frontdoor Test Verification and Anti-Mock Quality Gate
  As an engineering lead,
  I want "spec-ops test verify-frontdoors" and "spec-ops test audit-anti-mock" to audit the test suite,
  So that tests relying on prohibited internal monkey-patching, mock backdoors, or failing mutation kill thresholds are blocked before agents or developers can merge fragile code.

  Scenario: Passing Clean Blackbox Test Suite with Mutation Invariants
    Given a Python test suite where all feature tests interact exclusively through public frontdoors
    And no tests invoke "unittest.mock.patch" on internal module private methods
    And Mutmut mutation testing achieves >=80% mutant kill score on target domain modules
    When the lead runs "spec-ops test verify-frontdoors"
    Then the command exits with code 0
    And reports "Frontdoor Verification Passed: 0 private backdoors detected, Mutation Kill Score: 85%".

  Scenario: Blocking Tests with Prohibited Mock Backdoors and Private Method Spies
    Given an autonomous agent generates a test file in an active worktree
    And the test file imports private functions prefixed with "_" or uses "patch.object" on internal persistence adapters
    When the in-worktree preflight executes "spec-ops test verify-frontdoors"
    Then the command exits with code 1
    And prints a diagnostic violation citing ADR-0003 and the exact line numbers containing prohibited mocks
    And instructs the agent to exercise the feature exclusively through public entrypoints.

  Scenario: Mutation Score Threshold Enforcement
    Given a test suite verifying a domain state machine through public APIs
    And Mutmut identifies surviving mutants dropping the mutation score to 68% (below the 80% invariant)
    When the lead runs "spec-ops test verify-frontdoors --strict-mutation"
    Then the command exits with code 1
    And lists the surviving mutant IDs and untyped code branches requiring property or edge-case tests.

  Scenario: Scanning Test Tree with Audit Anti-Mock Command
    Given a test suite that exercises only public CLI and module frontdoors
    When "spec-ops test audit-anti-mock" scans the test tree
    Then zero anti-mock violations are reported.

  Scenario: Blocking Tests with Monkeypatching and Prohibited Mock Imports
    Given a test that monkeypatches private attributes or imports unittest.mock
    When anti-mock audit runs
    Then the test file is flagged with line numbers and commit is blocked.
