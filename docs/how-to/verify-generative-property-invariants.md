# How-To: Verify Generative Property Invariants

This guide explains how to execute Hypothesis generative property tests and invariant verification suites across pure domain models using `spec-ops verify --invariants`.

---

## 1. Run Invariant Verification

To run property invariant verification suites across all core domain state machines, parsers, and health algorithms:

```bash
spec-ops verify --invariants
```

Alternatively, invoke via the test subcommand:

```bash
spec-ops test properties
```

When tests execute, Hypothesis exercises randomized input generation to explore edge cases and invariant boundaries. If all generative property invariants hold, the command exits with code `0`.

---

## 2. Adjust Generation Example Counts

By default, the property verification runner evaluates 100 randomized examples per invariant. For intensive preflight checks or deep bug-hunting sessions, scale up the example threshold:

```bash
spec-ops verify --invariants --max-examples 200
```

---

## 3. Filter Target Invariant Suites

To target specific invariant test modules or filter by invariant property expression (using standard pytest `-k` filtering):

```bash
spec-ops verify --invariants -k event_bus
```

Or target a specific test path:

```bash
spec-ops verify --invariants tests/test_event_bus_properties.py
```

---

## 4. Export Machine-Readable Telemetry

For integration into autonomous worker loops, CI gate reporting, or IDE plugins, emit machine-readable JSON telemetry:

```bash
spec-ops verify --invariants --json
```

Example JSON output structure:

```json
{
  "total_properties": 48,
  "passed": 48,
  "failed": 0,
  "shrunk_counterexamples": []
}
```
