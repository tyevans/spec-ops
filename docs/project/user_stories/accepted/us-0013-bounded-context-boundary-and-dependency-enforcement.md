---
id: '0013'
title: Bounded Context Boundary and Dependency Direction Enforcement
status: Accepted
created: 2026-09-29
persona: Alex (The Agentic Systems Architect)
feature: FEAT-DDD-01
governing_prd: PRD-0005
---

# US-0013 — Bounded Context Boundary and Dependency Direction Enforcement

## Governing PRD
- [`PRD-0005: Relational Knowledge Graph, Architectural Profiles & Living Reporting`](../../product/accepted/prd-0005-relational-knowledge-graph-architectural-profiles-and-living-reporting.md)

## User Story

**As an** agentic systems architect,  
**I want** `spec-ops health` to statically verify bounded context import boundaries and dependency directions defined in `specops.toml`,  
**So that** autonomous coding agents and human engineers cannot introduce forbidden cross-context couplings, circular dependencies, or infrastructure leaks into pure domain models.

## Acceptance Criteria

```gherkin
Scenario: Clean repository verifying bounded context isolation
Given "specops.toml" defines bounded contexts "billing" and "orders"
And specifies that "orders.domain" cannot import from "orders.infrastructure" or "billing.*"
And all source imports strictly honor these dependency directions
When the architect runs "spec-ops health --architecture"
Then the command exits with code 0
And reports "Invariant Met: Bounded context boundary rules validated with 0 violations".
```

```gherkin
Scenario: Catching illegal cross-context domain import in CI
Given an autonomous agent introduces an import "from billing.infrastructure import StripeClient" into "src/orders/domain/order_aggregate.py"
When the preflight command runs "spec-ops health --architecture"
Then the command exits with code 1
And identifies the violating file "src/orders/domain/order_aggregate.py"
And reports "Architecture Invariant Violated: Domain layer cannot import external infrastructure 'billing.infrastructure'".
```

```gherkin
Scenario: Detecting circular bounded context dependencies
Given module "src/auth/service.py" imports "src/users/manager.py"
And module "src/users/manager.py" imports "src/auth/token.py"
When the architect runs "spec-ops health --architecture"
Then the command exits with code 1
And reports "Cyclic Architecture Dependency Detected: auth <-> users".
```

## Rationale & Compelling Value
Autonomous agents often resolve coding tasks by grabbing any import that works, breaking Domain-Driven Design (ADR-0007). Static boundary verification turns architectural boundaries into deterministic gates.
