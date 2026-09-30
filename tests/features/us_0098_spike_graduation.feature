Feature: Empirical Spike Hypothesis Validation and Automated ADR Synthesis
  As an agentic systems architect
  I want to execute spec-ops spike graduate to evaluate empirical benchmark results against the spike hypothesis and synthesize an ADR
  So that validated architectural conclusions are permanently locked into the constitution and dependent tasks are unblocked

  Scenario: Successfully graduating a proven spike with empirical benchmark data into an ADR
    Given a completed spike "SPIKE-0002" with hypothesis "DuckDB outperforms SQLite for 1M graph node queries under 200ms"
    And the spike test suite in "spikes/spike_0002/test_spike.py" passes with recorded benchmark output: "p95 latency = 142ms"
    When Alex runs "spec-ops spike graduate SPIKE-0002 --result proven --title 'Adopt DuckDB for Graph Query Acceleration'"
    Then a new ADR file "docs/project/adrs/proposed/adr-0010-adopt-duckdb-for-graph-query-acceleration.md" is authored
    And the ADR context and decision sections cite the empirical benchmark findings from "SPIKE-0002"
    And "SPIKE-0002" is moved to "docs/project/backlog/complete/" with status "Graduated"
    And all downstream tasks in "docs/project/backlog/proposed/" listing "SPIKE-0002" as a dependency have that dependency resolved.

  Scenario: Documenting a disproven hypothesis with rationale and blocking dependent implementation slices
    Given an architectural spike "SPIKE-0003" with hypothesis "In-memory SQLite meets <10ms sync requirement"
    And benchmark testing reveals p95 latency is 85ms (failing hypothesis)
    When Alex runs "spec-ops spike graduate SPIKE-0003 --result disproven --notes 'SQLite locking caused 85ms p95 contention'"
    Then an informational ADR or Architectural Finding is generated documenting why SQLite was rejected
    And any proposed implementation tasks depending on SPIKE-0003 are marked "Blocked: Spike hypothesis failed"
    And the backlog curator is prevented from promoting blocked tasks to "Refined".

  Scenario: Cleaning up disposable spike worktree upon graduation
    Given "SPIKE-0002" has been successfully graduated into "ADR-0010"
    When graduation completes
    Then the ephemeral worktree ".worktrees/spike-0002" is removed cleanly
    And the spike branch "spike/SPIKE-0002" is tagged "spike/SPIKE-0002-graduated" for audit history.
