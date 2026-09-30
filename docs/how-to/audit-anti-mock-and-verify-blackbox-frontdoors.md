# How-To: Audit Anti-Mock Violations and Verify Blackbox Frontdoors

This guide explains how to audit your test suite for prohibited mock backdoors, verify blackbox frontdoors, and enforce mutation testing invariants per ADR-0003 and ADR-0009 using `spec-ops test audit-anti-mock` and `spec-ops test verify-frontdoors`.

---

## 1. Why Blackbox Frontdoors?

Autonomous coding agents often produce fragile tests that appear to pass by reaching into private internal methods (functions starting with `_`), monkeypatching persistence layers with `unittest.mock.patch`, or bypassing domain validations with mock backdoors.

Per **ADR-0003** (Blackbox Frontdoor Verification), all acceptance tests must interact exclusively with public contracts:
- Public CLI commands (`spec-ops ...`)
- Public API interfaces and domain model entrypoints
- Observable side effects (file outputs, exit codes, stdout/stderr)

SpecOps enforces this invariant with AST-based static analysis to reject backdoor mocks before changes can merge.

---

## 2. Scanning for Anti-Mock Violations

To audit your test directory for prohibited mocks, run:

```bash
uv run spec-ops test audit-anti-mock tests/
```

### Prohibited Patterns Detected
- **`unittest.mock` imports**: Direct use of `unittest.mock`, `mock.patch`, or `MagicMock`
- **Private method monkeypatching**: `monkeypatch.setattr(...)` targeting private methods (`_foo`)
- **Direct private symbol access**: Calling internal functions or accessing private attributes (`_internal_state`)
- **Mock backdoors**: Bypassing public CLI or domain validation gates

### Example Output on Violation
When a test violates ADR-0003, the audit reports precise line numbers and explanations:

```text
❌ Anti-Mock Audit Failed: 2 violation(s) detected across 1 file(s):
   tests/test_example.py:14: Prohibited 'unittest.mock' import detected.
   tests/test_example.py:28: Monkeypatching private attribute '_db_connection' is forbidden by ADR-0003.
   
💡 Fix: Exercise functionality through public CLI commands or public module entrypoints.
```

---

## 3. Verifying Blackbox Frontdoors and Mutation Quality

To run the unified verification gate that checks both anti-mock compliance and mutation kill thresholds:

```bash
uv run spec-ops test verify-frontdoors tests/
```

### Enforcing Strict Mutation Thresholds
To enforce the mandatory >=80% mutant kill score (ADR-0009) in CI pipelines:

```bash
uv run spec-ops test verify-frontdoors tests/ --strict-mutation --threshold 80
```

If surviving mutants reduce the kill score below the configured threshold, the command exits with code `1` and outputs surviving mutant IDs and code branches requiring stronger assertions or property tests.

---

## 4. Structured JSON Output for CI Integration

Both commands support `--json` for integration into automated CI gates and tooling dashboards:

```bash
uv run spec-ops test audit-anti-mock tests/ --json
```

```json
{
  "status": "failed",
  "violations_count": 2,
  "files_scanned": 48,
  "violations": [
    {
      "file": "tests/test_example.py",
      "line": 14,
      "rule": "ADR-0003",
      "description": "Prohibited 'unittest.mock' import detected"
    }
  ]
}
```

---

## 5. Traceability and Governance

- **Governing ADR**: [ADR-0003: Blackbox Frontdoor Verification](../project/adrs/accepted/0003-blackbox-frontdoor-verification.md)
- **Governing PRD**: [PRD-0005: Living Knowledge Graph, Advanced Multi-Agent Worker Fleets, and PMaC Scalability](../project/product/accepted/0005-living-knowledge-graph-and-multi-agent-scalability.md)
- **Governing Story**: [US-0020: Blackbox Frontdoor Test Verification and Anti-Mock Quality Gate](../project/user_stories/accepted/us-0020-ast-blackbox-frontdoor-test-verification-and-anti-mock-gate.md)
- **Implementing Task**: [TASK-0061](../project/backlog/complete/0061-property-invariants-mutation-quality-gate-and-anti-mock.md)
