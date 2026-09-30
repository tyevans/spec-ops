# How-To: Watch Workspace Changes and Stream Real-Time Graph Events

This guide explains how to run `spec-ops watch` to monitor specification changes and stream real-time graph events over the in-memory event bus.

---

## Running the Workspace Watcher

To boot the debounced workspace watcher with the default 250ms debounce window:

```bash
spec-ops watch
```

Or invoke via the graph namespace:

```bash
spec-ops graph watch
```

---

## Streaming JSON Graph Events

To emit structured JSON events to standard output (ideal for IDE servers, background daemons, and visualizer websocket bridges):

```bash
spec-ops watch --event-stream
```

Example JSON event output:

```json
{"event": "node_updated", "id": "TASK-0010", "type": "task", "status": "Refined", "edges_recalculated": 3}
```

---

## Customizing Debounce Windows

When performing large batch git checkouts or branch switches that modify dozens of specification files simultaneously, customize the debounce window:

```bash
spec-ops watch --debounce-ms 100
```

When a batch update completes, a summary is emitted without event storms:

```text
Batched update: 15 files synchronized in 42ms
```

---

## Immediate Warning Diagnostics

When specification edits introduce broken references or syntax errors, structured diagnostics are dispatched immediately without killing the watcher process:

```text
warning: Broken Reference Created in docs/project/user_stories/accepted/us-0060.md
-> References non-existent PRD: PRD-9999
UNANCHORED_REFERENCE_DETECTED: docs/project/user_stories/accepted/us-0060.md references non-existent PRD: PRD-9999
```

The affected in-memory node is flagged as `DRAFT_INVALID` until the missing entity is authored.
