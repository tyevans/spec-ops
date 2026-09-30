@us_0013 @architecture
Feature: Bounded Context Boundary and Dependency Direction Enforcement

  Scenario: Clean repository verifying bounded context isolation
    Given "specops.toml" defines bounded contexts "billing" and "orders"
    And specifies that "orders.domain" cannot import from "orders.infrastructure" or "billing.*"
    And all source imports strictly honor these dependency directions
    When the architect runs "spec-ops health --architecture"
    Then the command exits with code 0
    And reports "Invariant Met: Bounded context boundary rules validated with 0 violations"

  Scenario: Catching illegal cross-context domain import in CI
    Given an autonomous agent introduces an import "from billing.infrastructure import StripeClient" into "src/orders/domain/order_aggregate.py"
    When the preflight command runs "spec-ops health --architecture"
    Then the command exits with code 1
    And identifies the violating file "src/orders/domain/order_aggregate.py"
    And reports "Architecture Invariant Violated: Domain layer cannot import external infrastructure 'billing.infrastructure'"

  Scenario: Detecting circular bounded context dependencies
    Given module "src/auth/service.py" imports "src/users/manager.py"
    And module "src/users/manager.py" imports "src/auth/token.py"
    When the architect runs "spec-ops health --architecture"
    Then the command exits with code 1
    And reports "Cyclic Architecture Dependency Detected: auth <-> users"
