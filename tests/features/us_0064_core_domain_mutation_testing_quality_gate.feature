@us_0064 @core @mutation
Feature: Core Domain Mutation Testing Invariant and Mutant Kill Score Quality Gate

  Scenario: Passing the mutation quality gate on core domain modules
    Given the test suite covers all public methods of "src/spec_ops/core/"
    When the lead runs "spec-ops invariants verify-mutations --threshold 80"
    Then Mutmut injects synthetic mutants into "models.py", "parser.py", and "graph.py"
    And tests kill at least 80% of all generated mutants
    And the command exits with code 0
    And reports "Mutation Invariant Met: 84% mutant kill score (168 killed, 32 survived, 0 timed out)".

  Scenario: Blocking pull request when weak assertions leave surviving mutants below threshold
    Given a pull request modifies "src/spec_ops/core/graph.py" adding a new edge filtering option
    And the author adds tests that execute the code but make no assertions on the filtered edge types
    When CI executes "spec-ops invariants verify-mutations --threshold 80"
    Then Mutmut detects 12 surviving mutants in the unasserted filter branch
    And the mutant kill score drops to 71% (below the 80% invariant threshold)
    And the command exits with code 1
    And prints surviving mutant diffs and exact line numbers requiring stronger blackbox assertions.

  Scenario: Generating machine-readable mutation score report for CI telemetry
    Given a completed mutation test run on "src/spec_ops/core/"
    When the lead runs "spec-ops invariants verify-mutations --json"
    Then the command outputs valid JSON containing:
      | field            |
      | target_module    |
      | mutation_score   |
      | threshold        |
      | killed_count     |
      | survived_count   |
      | survived_mutants |

  Scenario: Passing the mutation quality gate on core domain modules via test mutation
    Given core domain modules with high-fidelity blackbox test suites
    When "spec-ops test mutation --threshold 80" runs
    Then mutants are generated, killed by tests, and the command exits with code 0

  Scenario: Blocking weak assertions via test mutation command
    Given a test suite with tautological or weak assertions
    When mutation score falls below 80%
    Then the command fails with a detailed breakdown of surviving mutants
