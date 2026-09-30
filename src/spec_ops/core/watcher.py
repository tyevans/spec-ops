"""Workspace change watcher and real-time graph event coordinator.

Governed by ADR-0001, ADR-0003, ADR-0007, ADR-0008; PRD-0005; US-0065.
Target Bounded Context: core. File length strictly under 400 lines.
"""

from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

from .event_bus import (
    BATCHED_UPDATE,
    GRAPH_CYCLE_INTRODUCED,
    NODE_UPDATED,
    TASK_PROMOTED,
    UNANCHORED_REFERENCE_DETECTED,
    Debouncer,
    EventBus,
    GraphEvent,
    InMemoryGraphState,
)

logger = logging.getLogger(__name__)

EXCLUDE_FILENAMES = {
    "REGISTRY.md",
    "FEATURE_INVENTORY.md",
    "README.md",
    "PRIORITY.md",
    "ROADMAP.md",
}


class WorkspaceWatcher:
    """Watches workspace specification files and dispatches in-memory graph events."""

    def __init__(
        self,
        root_dir: Path,
        debounce_ms: float = 250.0,
        event_stream: bool = False,
        event_bus: EventBus | None = None,
        out_stream: Any = None,
        err_stream: Any = None,
    ) -> None:
        self.root_dir = root_dir.resolve()
        self.docs_dir = self.root_dir / "docs" / "project"
        self.debounce_ms = max(0.0, float(debounce_ms))
        self.event_stream = event_stream
        self.event_bus = event_bus or EventBus()
        self.out_stream = out_stream or sys.stdout
        self.err_stream = err_stream or sys.stderr
        self.state = InMemoryGraphState(self.root_dir)
        self._debouncer = Debouncer(debounce_ms=self.debounce_ms, on_flush=self._handle_batch_flush)
        self._stop_event = threading.Event()
        self._file_snapshots: dict[Path, tuple[int, int]] = {}
        self._old_sigint: Any = None
        self._old_sigterm: Any = None
        self._register_event_handlers()

    def _register_event_handlers(self) -> None:
        self.event_bus.subscribe(TASK_PROMOTED, self._on_task_promoted)
        self.event_bus.subscribe(NODE_UPDATED, self._on_node_updated)
        self.event_bus.subscribe(UNANCHORED_REFERENCE_DETECTED, self._on_unanchored_reference)
        self.event_bus.subscribe(GRAPH_CYCLE_INTRODUCED, self._on_graph_cycle)
        self.event_bus.subscribe(BATCHED_UPDATE, self._on_batched_update)

    def _on_task_promoted(self, event: GraphEvent) -> None:
        if not self.event_stream:
            prev = event.payload.get("previous_status", "Unknown")
            curr = event.payload.get("new_status", event.status or "Refined")
            print(f"[TASK_PROMOTED] {event.entity_id}: {prev} -> {curr}", file=self.out_stream, flush=True)

    def _on_node_updated(self, event: GraphEvent) -> None:
        if self.event_stream:
            print(event.to_json(), file=self.out_stream, flush=True)

    def _on_unanchored_reference(self, event: GraphEvent) -> None:
        payload = event.payload
        src_file = payload.get("source_file", "")
        tgt_type = payload.get("target_type", "PRD")
        missing = payload.get("missing_ref", "")
        msg = f"warning: Broken Reference Created in {src_file}\n-> References non-existent {tgt_type}: {missing}\nUNANCHORED_REFERENCE_DETECTED: {src_file} references non-existent {tgt_type}: {missing}"
        print(msg, file=self.err_stream, flush=True)

    def _on_graph_cycle(self, event: GraphEvent) -> None:
        path_str = event.payload.get("path_str", "")
        print(f"warning: Cyclic dependency introduced in graph: {path_str}", file=self.err_stream, flush=True)

    def _on_batched_update(self, event: GraphEvent) -> None:
        count = event.payload.get("files_count", 0)
        ms = round(event.payload.get("duration_ms", 0.0))
        print(f"Batched update: {count} files synchronized in {ms}ms", file=self.out_stream, flush=True)

    def _handle_batch_flush(self, changed_paths: list[Path]) -> None:
        t0 = time.perf_counter()
        self.state.apply_file_changes(changed_paths, event_bus=self.event_bus)
        duration_ms = (time.perf_counter() - t0) * 1000.0
        if len(changed_paths) > 1:
            self.event_bus.publish(
                GraphEvent(
                    event_type=BATCHED_UPDATE,
                    payload={"files_count": len(changed_paths), "duration_ms": duration_ms},
                )
            )

    def _scan_disk_files(self) -> dict[Path, tuple[int, int]]:
        files: dict[Path, tuple[int, int]] = {}
        if not self.docs_dir.exists():
            return files
        for dirpath, _, filenames in os.walk(str(self.docs_dir)):
            for fn in filenames:
                if fn.endswith(".md") and not fn.startswith(".") and fn not in EXCLUDE_FILENAMES:
                    fp = Path(dirpath) / fn
                    try:
                        st = fp.stat()
                        files[fp] = (st.st_mtime_ns, st.st_size)
                    except OSError:
                        pass
        return files

    def scan_once(self) -> list[Path]:
        current_files = self._scan_disk_files()
        changed: list[Path] = []

        for p, stat in current_files.items():
            if p not in self._file_snapshots or self._file_snapshots[p] != stat:
                changed.append(p)

        for p in self._file_snapshots:
            if p not in current_files:
                changed.append(p)

        self._file_snapshots = current_files

        for p in changed:
            self._debouncer.add(p)

        return changed

    def start(self) -> None:
        self.state.load_initial_state()
        self._file_snapshots = self._scan_disk_files()

        def _handle_signal(sig: int, frame: Any) -> None:
            self.stop()

        try:
            self._old_sigint = signal.signal(signal.SIGINT, _handle_signal)
            self._old_sigterm = signal.signal(signal.SIGTERM, _handle_signal)
        except (ValueError, AttributeError):
            pass

    def stop(self) -> None:
        self._stop_event.set()
        self._debouncer.cancel()
        try:
            if self._old_sigint is not None:
                signal.signal(signal.SIGINT, self._old_sigint)
            if self._old_sigterm is not None:
                signal.signal(signal.SIGTERM, self._old_sigterm)
        except (ValueError, AttributeError):
            pass

    def run(self, max_iterations: int | None = None, poll_interval_s: float = 0.05) -> int:
        self.start()
        iterations = 0
        try:
            while not self._stop_event.is_set():
                self.scan_once()
                iterations += 1
                if max_iterations is not None and iterations >= max_iterations:
                    break
                self._stop_event.wait(poll_interval_s)

            if self._debouncer.is_pending():
                items = self._debouncer.flush()
                self._handle_batch_flush(items)
        finally:
            self.stop()
        return 0
