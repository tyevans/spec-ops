# How-To: Export Structured Event Audit Sink Archives

This guide explains how to export, filter, and compress immutable event ledgers into structured audit sink archives using `spec-ops audit sink` governed by [ADR-0010](../project/adrs/accepted/adr-0010-pure-decider-event-sourced-kernel.md).

---

## Overview

SpecOps maintains an immutable, event-sourced audit ledger of all task state transitions, preflights, and security checks (`.specops/events.db`). The audit sink exporter extracts these events into standardized, cryptographically chained archives suitable for external compliance storage or offline analysis.

Every exported record contains:
- Monotonic sequence numbers (`1..N`)
- Cryptographic SHA-256 sequence hash chaining (`prev_hash:seq:event_id:event_type:payload`)
- Standardized metadata (event type, aggregate, category, timestamp)

---

## Exporting Events to Structured JSONL

To export all lifecycle transitions to a JSON Lines archive:

```bash
uv run spec-ops audit sink --format jsonl --output dist/audit/audit-sink.jsonl
```

Example output:
```text
✨ Exported 42 structured audit events to dist/audit/audit-sink.jsonl (6,240 bytes)
   Format:       JSONL
   Chained Hash: 8f9b4e2a1c0d...
   Status:       OK
```

---

## Compressed Export for Archival

To generate gzip-compressed archives:

```bash
uv run spec-ops audit sink --compress --output dist/audit/audit-sink.jsonl.gz
```

---

## Exporting to Independent SQLite Snapshot

To generate an isolated, vacuumed SQLite snapshot database with indexed categories and timestamps:

```bash
uv run spec-ops audit sink --format sqlite --output dist/audit/audit-sink.sqlite
```

---

## Filtering by Category, Aggregate Type, or Date

You can slice the exported stream by category (`security`, `worker`, `backlog`), aggregate type, or date range:

```bash
# Export only security scan and attestation records
uv run spec-ops audit sink --category security --output dist/audit/security-audit.jsonl

# Export events since a specific date
uv run spec-ops audit sink --since 2026-10-01 --output dist/audit/recent-audit.jsonl
```

---

## Programmatic Verification

To programmatically verify cryptographic integrity and chained sequence hashes:

```python
from spec_ops.core.audit_sink import read_audit_sink, verify_audit_sink

entries = read_audit_sink("dist/audit/audit-sink.jsonl")
valid, msg = verify_audit_sink(entries)
assert valid is True, msg
```
