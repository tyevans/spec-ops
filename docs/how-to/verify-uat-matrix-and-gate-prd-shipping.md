# How-To: Verify Living Customer UAT Matrix and Gate PRD Shipping

This guide shows how to inspect customer UAT verification readiness across accepted PRDs and enforce automated shipping gates before transitioning product specifications to shipped status.

---

## 1. Inspecting Customer UAT Readiness in the Living Visualizer

SpecOps provides a dedicated Customer UAT tab in the living 2D visualizer that correlates accepted PRD business outcomes against passing Gherkin acceptance criteria and stakeholder sign-offs:

1. Launch the living visualizer:
   ```bash
   spec-ops visualizer
   ```
2. Navigate to the **Customer UAT Matrix** tab (`#uat`).
3. Inspect each outcome's three-part verification gate:
   - **BDD Scenario Execution**: Automated Gherkin test pass rate (`pytest-bdd`).
   - **Stakeholder Sign-Off**: Verification recorded in `docs/project/product/uat-signoff.json`.
   - **Release Receipt Provenance**: Cryptographic manifest verification linking commits and test runs.

---

## 2. Enforcing Customer UAT Verification Gates in Preflight CI

To prevent premature shipping of incomplete product outcomes in automated CI/CD pipelines, execute the preflight health check with UAT enforcement:

```bash
spec-ops health --check-uat
```

If any outcome in an accepted PRD lacks an approved stakeholder sign-off or associated passing BDD scenario, the command reports actionable diagnostic warnings and exits with a non-zero code.

---

## 3. Automated PRD Shipping Gate

When all backlog tasks for an accepted PRD are marked complete and all customer UAT gates pass, transition the PRD to shipped:

```bash
spec-ops prd ship PRD-0003
```

The shipping gate automatically performs the following atomic operations:
1. **Backlog Integrity Check**: Verifies that 100% of implementing tasks in `docs/project/backlog/complete/` are resolved.
2. **Customer UAT Gate**: Confirms all business outcomes cite passing Gherkin test runs and valid PM sign-offs.
3. **Atomic Relocation**: Moves `docs/project/product/accepted/prd-XXXX-*.md` to `docs/project/product/shipped/`.
4. **Relational Graph Synchronization**: Updates PRD status metadata in the living knowledge graph.

If outstanding tasks remain incomplete or UAT sign-offs are missing, the command aborts without moving the specification file:

```
❌ Cannot ship PRD-0003: 2 tasks remaining in refined/ or proposed/ buffer.
```
