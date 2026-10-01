"""Real-time workspace file watcher and incremental graph invalidation engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0011, ADR-0015; PRD-0005; US-0059, US-0060.
Target Bounded Context: graph. File length strictly under 400 lines.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import re
import signal
import sys
import threading
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from ..core.cache import (
    _build_cache_entry,
    _deserialize_entity,
    compute_cache_checksum,
    compute_content_sha256,
)
from ..core.graph import process_project_graph
from ..core.models import ProjectData
from ..core.parser import (
    parse_adr,
    parse_personas,
    parse_prd,
    parse_priority_ranks,
    parse_task,
    parse_user_story,
)

logger = logging.getLogger(__name__)

EXCLUDE_DOC_FILES = {
    "REGISTRY.md",
    "FEATURE_INVENTORY.md",
    "README.md",
    "PRIORITY.md",
    "ROADMAP.md",
}


@dataclass
class GraphChangeEvent:
    """Represents a structured graph cache invalidation or update event."""

    event: str
    path: str
    entity_id: str
    sha256: str
    duration_ms: float
    invalidated: int
    timestamp: str = ""

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class IncrementalGraphInvalidator:
    """Selectively invalidates and re-extracts graph entities in .specops/cache/graph.json."""

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = root_dir.resolve()
        self.cache_file = self.root_dir / ".specops" / "cache" / "graph.json"
        self.docs_dir = self.root_dir / "docs" / "project"
        self.src_dir = self.root_dir / "src"
        self._cached_payload: dict[str, Any] | None = None

    def load_cache(self) -> dict[str, Any]:
        """Loads and verifies existing cache payload, building cold cache if missing."""
        if self._cached_payload is not None:
            return self._cached_payload
        if self.cache_file.exists():
            try:
                payload = json.loads(self.cache_file.read_text(encoding="utf-8"))
                if isinstance(payload, dict) and payload.get("checksum") == compute_cache_checksum(payload):
                    self._cached_payload = payload
                    return payload
            except Exception as exc:
                logger.warning("Corrupt graph cache in %s: %s", self.cache_file, exc)

        from ..core.cache import RelationalGraphCacheEngine

        engine = RelationalGraphCacheEngine(self.root_dir)
        engine.compile_graph(force_cold=True)
        try:
            self._cached_payload = json.loads(self.cache_file.read_text(encoding="utf-8"))
            return self._cached_payload
        except Exception:
            self._cached_payload = {"version": 1, "entities": {}, "edges": [], "checksum": ""}
            return self._cached_payload

    def save_cache(self, payload: dict[str, Any]) -> None:
        """Persists cache payload with deterministic checksum."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        payload["checksum"] = compute_cache_checksum(payload)
        self.cache_file.write_text(json.dumps(payload), encoding="utf-8")
        self._cached_payload = payload

    def _detect_entity_type(self, path: Path) -> str:
        if path.name in EXCLUDE_DOC_FILES or path.name.startswith("."):
            return ""
        if path.name == "PERSONAS.md":
            return "persona"
        parts = path.parts
        if "user_stories" in parts:
            return "story"
        if "product" in parts:
            return "prd"
        if "adrs" in parts:
            return "adr"
        if "backlog" in parts:
            return "task"
        return ""

    def _parse_single_spec(self, etype: str, path: Path) -> Any:
        try:
            if etype == "persona":
                return parse_personas(path)
            if etype == "prd":
                return parse_prd(path)
            if etype == "story":
                return parse_user_story(path)
            if etype == "adr":
                return parse_adr(path)
            if etype == "task":
                b_dir = self.docs_dir / "backlog"
                ranks = parse_priority_ranks(b_dir) if b_dir.exists() else {}
                m = re.match(r"^(\d+)", path.stem)
                cid = f"TASK-{m.group(1).zfill(4)}" if m else path.stem
                return parse_task(path, priority_rank=ranks.get(cid, 999999))
        except Exception as exc:
            logger.warning("Failed parsing %s (%s): %s", path, etype, exc)
        return None

    def _update_dependents_and_edges(self, cache: dict[str, Any]) -> None:
        entities: dict[str, Any] = dict(sorted(cache.get("entities", {}).items()))
        cache["entities"] = entities
        canon_map = {ent["canonical_id"]: ent for ent in entities.values() if "canonical_id" in ent}
        for e in entities.values():
            e["dependents"] = []
        for e in entities.values():
            cid = e.get("canonical_id", "")
            for dep in e.get("dependencies", []):
                clean = dep.replace("TASK-", "").lstrip("0")
                canon = f"TASK-{clean.zfill(4)}" if clean and dep.startswith("TASK-") else dep
                target = canon_map.get(canon)
                if target and cid not in target["dependents"]:
                    target["dependents"].append(cid)

        data = ProjectData()
        for centry in entities.values():
            etype = centry.get("entity_type")
            cdata = centry.get("data")
            if not cdata:
                continue
            if etype == "persona":
                plist = cdata if isinstance(cdata, list) else [cdata]
                data.personas.extend([_deserialize_entity("persona", copy.deepcopy(p)) for p in plist])
            elif etype:
                attr = "stories" if etype == "story" else f"{etype}s"
                if hasattr(data, attr):
                    getattr(data, attr).append(_deserialize_entity(etype, copy.deepcopy(cdata)))

        process_project_graph(data)
        cache["edges"] = [
            {
                "source_type": e.source_type,
                "source_id": e.source_id,
                "target_type": e.target_type,
                "target_id": e.target_id,
                "relation": e.relation,
            }
            for e in data.edges
        ]

    def invalidate_file(self, file_path: Path | str) -> dict[str, Any]:
        """Incrementally invalidates a single file and updates .specops/cache/graph.json."""
        t0 = time.perf_counter()
        p = Path(file_path)
        if not p.is_absolute():
            p = (self.root_dir / p).resolve()
        else:
            p = p.resolve()

        try:
            rel = str(p.relative_to(self.root_dir))
        except ValueError:
            rel = str(p)

        cache = self.load_cache()
        entities: dict[str, Any] = cache.setdefault("entities", {})
        file_hashes: dict[str, str] = cache.setdefault("file_hashes", {})

        if not p.exists():
            if rel in entities:
                cid = entities[rel].get("canonical_id", "")
                del entities[rel]
                file_hashes.pop(rel, None)
                self._update_dependents_and_edges(cache)
                self.save_cache(cache)
                ms = (time.perf_counter() - t0) * 1000.0
                return GraphChangeEvent("deleted", rel, cid, "", ms, 1).to_dict()
            ms = (time.perf_counter() - t0) * 1000.0
            return GraphChangeEvent("ignored", rel, "", "", ms, 0).to_dict()

        content = p.read_bytes()
        new_sha = compute_content_sha256(content)
        st = p.stat()

        if rel in entities and entities[rel].get("sha256") == new_sha:
            if entities[rel].get("mtime_ns") != st.st_mtime_ns or entities[rel].get("size") != st.st_size:
                entities[rel]["mtime_ns"] = st.st_mtime_ns
                entities[rel]["size"] = st.st_size
                self.save_cache(cache)
            cid = entities[rel].get("canonical_id", "")
            ms = (time.perf_counter() - t0) * 1000.0
            return GraphChangeEvent("unchanged", rel, cid, new_sha, ms, 0).to_dict()

        is_src = rel.startswith("src/") or rel == "src" or (self.src_dir.exists() and p.is_relative_to(self.src_dir))
        if is_src:
            file_hashes[rel] = new_sha
            self.save_cache(cache)
            ms = (time.perf_counter() - t0) * 1000.0
            return GraphChangeEvent("modified", rel, f"code:{rel}", new_sha, ms, 1).to_dict()

        etype = self._detect_entity_type(p)
        if not etype:
            ms = (time.perf_counter() - t0) * 1000.0
            return GraphChangeEvent("ignored", rel, "", new_sha, ms, 0).to_dict()

        parsed = self._parse_single_spec(etype, p)
        if parsed is None:
            ms = (time.perf_counter() - t0) * 1000.0
            return GraphChangeEvent("error", rel, "", new_sha, ms, 0).to_dict()

        _, centry = _build_cache_entry(rel, new_sha, etype, parsed, st=st)
        entities[rel] = centry
        file_hashes[rel] = new_sha

        self._update_dependents_and_edges(cache)
        self.save_cache(cache)

        cid = centry.get("canonical_id", "")
        ms = (time.perf_counter() - t0) * 1000.0
        return GraphChangeEvent("modified", rel, cid, new_sha, ms, 1).to_dict()


class WorkspaceGraphWatcher:
    """Watches docs/project/ and src/ for changes, incrementally synchronizing graph cache."""

    def __init__(
        self,
        root_dir: Path,
        interval: float = 0.5,
        debounce_ms: float = 250.0,
        json_output: bool = False,
        out_stream: Any = None,
        invalidator: IncrementalGraphInvalidator | None = None,
        on_event: Callable[[dict[str, Any]], None] | None = None,
    ) -> None:
        self.root_dir = root_dir.resolve()
        self.docs_dir = self.root_dir / "docs" / "project"
        self.src_dir = self.root_dir / "src"
        self.interval = max(0.01, float(interval))
        self.debounce_ms = max(0.0, float(debounce_ms))
        self.json_output = json_output
        self.out_stream = out_stream or sys.stdout
        self.invalidator = invalidator or IncrementalGraphInvalidator(self.root_dir)
        self.on_event = on_event
        self._stop_event = threading.Event()
        self._file_snapshots: dict[Path, tuple[int, int]] = {}
        self._old_sigint: Any = None
        self._old_sigterm: Any = None

    def _scan_paths(self) -> dict[Path, tuple[int, int]]:
        files: dict[Path, tuple[int, int]] = {}
        for target_dir in (self.docs_dir, self.src_dir):
            if not target_dir.exists():
                continue
            for root, _, filenames in os.walk(str(target_dir)):
                for fn in filenames:
                    if fn.startswith(".") or fn.endswith(".pyc") or fn in ("__pycache__", "REGISTRY.md", "ROADMAP.md", "PRIORITY.md"):
                        continue
                    if target_dir == self.docs_dir and not fn.endswith(".md"):
                        continue
                    p = Path(root) / fn
                    try:
                        st = p.stat()
                        files[p] = (st.st_mtime_ns, st.st_size)
                    except OSError:
                        pass
        return files

    def scan_once(self) -> list[dict[str, Any]]:
        """Performs a single filesystem scan, invalidating any modified, created, or deleted files."""
        current_files = self._scan_paths()
        events: list[dict[str, Any]] = []

        for p, stat in current_files.items():
            if p not in self._file_snapshots or self._file_snapshots[p] != stat:
                evt = self.invalidator.invalidate_file(p)
                if evt.get("event") in ("modified", "created"):
                    events.append(evt)
                    self._emit_event(evt)

        for p in list(self._file_snapshots.keys()):
            if p not in current_files:
                evt = self.invalidator.invalidate_file(p)
                if evt.get("event") == "deleted":
                    events.append(evt)
                    self._emit_event(evt)

        self._file_snapshots = current_files
        return events

    def _emit_event(self, evt: dict[str, Any]) -> None:
        if self.json_output:
            print(json.dumps(evt), file=self.out_stream, flush=True)
        else:
            print(
                f"[GRAPH_SYNC] {evt.get('path')}: {evt.get('entity_id')} synchronized in {evt.get('duration_ms', 0):.2f}ms",
                file=self.out_stream,
                flush=True,
            )
        if self.on_event:
            self.on_event(evt)

    def start(self) -> None:
        """Initializes cache snapshot and signal handlers."""
        self.invalidator.load_cache()
        if not self._file_snapshots:
            self._file_snapshots = self._scan_paths()

        def _handle_signal(sig: int, frame: Any) -> None:
            self.stop()

        try:
            self._old_sigint = signal.signal(signal.SIGINT, _handle_signal)
            self._old_sigterm = signal.signal(signal.SIGTERM, _handle_signal)
        except (ValueError, AttributeError):
            pass

    def stop(self) -> None:
        """Stops the watcher polling loop."""
        self._stop_event.set()
        try:
            if self._old_sigint is not None:
                signal.signal(signal.SIGINT, self._old_sigint)
            if self._old_sigterm is not None:
                signal.signal(signal.SIGTERM, self._old_sigterm)
        except (ValueError, AttributeError):
            pass

    def run(self, max_iterations: int | None = None) -> int:
        """Runs the monitoring loop until stopped or max_iterations reached."""
        self.start()
        iterations = 0
        try:
            while not self._stop_event.is_set():
                if self.debounce_ms > 0:
                    time.sleep(self.debounce_ms / 1000.0)
                self.scan_once()
                iterations += 1
                if max_iterations is not None and iterations >= max_iterations:
                    break
                self._stop_event.wait(self.interval)
        finally:
            self.stop()
        return 0


# Export aliases
IncrementalInvalidator = IncrementalGraphInvalidator
WorkspaceWatcher = WorkspaceGraphWatcher
