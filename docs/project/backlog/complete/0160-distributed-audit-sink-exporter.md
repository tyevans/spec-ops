---
id: '0160'
title: Distributed Event Bus and Structured Audit Sink Exporter
status: Complete
dependencies:
- TASK-0132
- TASK-0154
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0007
- ADR-0010
governing_prds:
- PRD-0001
- PRD-0006
governing_stories:
- US-0117
target_bc: core
signed_off_by: Ty Evans <tyevans@gmail.com>
signed_off_at: '2026-10-02T00:36:59.792674+00:00'
commit_signature_status: SIGNED
has_signed_commits: true
---

# TASK-0160: Distributed Event Bus and Structured Audit Sink Exporter

## Summary
Implement a structured event audit sink exporter and historical stream compressor (`src/spec_ops/core/audit_sink.py`). Governed by ADR-0010 and PRD-0001, this engine exports pure decider lifecycle events, state transitions, and preflight audit records into structured JSONL or SQLite audit archives (`spec-ops audit sink`).

## Problem Statement & Context
As multi-worker fleets and orchestrator loops execute continuous development cycles, thousands of lifecycle events accumulate. Compliance and telemetry require immutable, compressed, and queryable audit trails that can be archived to external compliance storage or inspected during post-mortems without bloating git repositories.

## Key Requirements & Scope
1. **Audit Sink Exporter (`src/spec_ops/core/audit_sink.py`)**:
   - Reads event ledger records from embedded SQLite or JSONL event stores.
   - Formats events into standardized structured audit entries with cryptographic sequence numbers.
   - Supports compressed gzip JSONL export and SQLite vacuumed snapshots.
   - Filters events by date range, aggregate type, or event category.
2. **Audit Sink CLI (`spec-ops audit sink [--format jsonl|sqlite] [--output <path>] [--since <date>] [--compress]`)**:
   - Executes audit stream export and reports total exported records and file size.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate verifying export accuracy and schema fidelity.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Module in `src/spec_ops/core/audit_sink.py` must stay strictly under 400 lines (ADR-0002).
- **Event-Sourced Kernel (ADR-0010)**: Export reads from immutable event journals without modifying past events.
- **Mutation Testing Scope**: Target module `src/spec_ops/core/audit_sink.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Exporting decider events to structured JSONL audit sink
```gherkin
Given an event store with recorded lifecycle transitions
When the developer runs spec-ops audit sink with JSONL format
Then all events are exported into structured lines with sequence numbers and timestamps
And the command terminates with exit code 0
```

### Scenario 2: Filtering exported events by category
```gherkin
Given an event store containing worker, security, and backlog events
When the developer exports events filtered to security events
Then only matching security audit events are emitted to the output file
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary list of event records, exporting and re-reading the audit sink produces identical event payload sequences without corruption.
