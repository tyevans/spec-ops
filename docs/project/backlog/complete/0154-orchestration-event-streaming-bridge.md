---
id: '0154'
title: Real-Time Orchestration Event Streaming and WebSocket Telemetry Bridge
status: Complete
dependencies:
- TASK-0114
- TASK-0132
governing_adrs:
- ADR-0001
- ADR-0002
- ADR-0003
- ADR-0010
governing_prds:
- PRD-0006
governing_stories:
- US-0115
- US-0117
target_bc: core
signed_off_by: Ty Evans <tyler@poorlythoughtout.com>
signed_off_at: '2026-10-01T11:00:00+00:00'
has_signed_commits: true
commit_signature_status: SIGNED
---

# TASK-0154: Real-Time Orchestration Event Streaming and WebSocket Telemetry Bridge

## Summary
Implement the real-time orchestration event streaming and telemetry bridge (`src/spec_ops/core/event_streamer.py`). Governed by ADR-0010 and PRD-0006, this engine connects the event-sourced backlog kernel and autonomous worker lifecycle to server-sent events (SSE) and WebSocket feeds, streaming real-time task transitions, preflight results, and worker telemetry to the local visualizer and monitoring dashboards.

## Problem Statement & Context
As multi-agent orchestration scales, human supervisors and peer agents need live, streaming visibility into worker progress, test execution attempts, and task claims without polling the disk or reading raw logs. Building upon the pure event-sourced substrate from ADR-0010, an embedded streaming bridge provides instant pub/sub telemetry to external dashboards and visualizers.

## Key Requirements & Scope
1. **Pub/Sub Event Streaming Bridge (`src/spec_ops/core/event_streamer.py`)**:
   - Subscribes to `eventsource-py` domain events (`TaskProposed`, `TaskRefined`, `TaskClaimed`, `TaskCompleted`, `TaskReleased`).
   - Broadcasts JSON-serialized event envelopes over async queue consumers.
   - Provides HTTP SSE endpoint (`/api/events/stream`) in the embedded visualizer server.
2. **Event Replay & Snapshot Capability**:
   - Allows clients connecting mid-session to replay the last $N$ events from `.specops/events.db` to reconstruct current fleet state.
3. **Blackbox Frontdoor Verification**:
   - 100% test pass rate with zero mock backdoors.

## Architectural Invariants & Seams
- **File Length Limit (<500 lines)**: Event streaming module in `src/spec_ops/core/event_streamer.py` must stay strictly under 400 lines (ADR-0002).
- **Zero-Daemon Local Principle (ADR-0010)**: Operates asynchronously within the embedded SpecOps visualizer without requiring external message brokers (e.g. Kafka or Redis).
- **Mutation Testing Scope**: Target modules for mutmut mutation testing include `src/spec_ops/core/event_streamer.py` with target >=80% mutant kill score (ADR-0009).

## Acceptance Criteria

### Scenario 1: Streaming task lifecycle events to connected clients
```gherkin
Given a running SpecOps event streaming bridge
When a task transitions from refined to claimed
Then a TaskClaimed event envelope is published to the stream in under 20 milliseconds
And connected subscribers receive the serialized event payload
```

### Scenario 2: Historical event replay on new subscriber connection
```gherkin
Given an existing event store containing historical task lifecycle events
When a new subscriber connects with a replay request
Then the bridge streams past events in monotonic sequence order
And transitions to live streaming seamlessly
```

## Hypothesis Invariant Properties

- `@given(...)`: Generative property tests asserting that for any arbitrary stream of domain events, serialized event envelopes preserve exact aggregate IDs, sequence versions, and event types without data truncation.
