"""Incremental DAG topological cache and sub-millisecond Tarjan cycle pre-check engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0017; PRD-0005; US-0058.
File length strictly under 400 lines.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
import hashlib
import json
import logging
from pathlib import Path
import re
import time
from typing import Any

from .parser import extract_frontmatter
from .topology import compute_execution_tiers

logger = logging.getLogger(__name__)


class CyclicDependencyError(Exception):
    """Domain violation error raised when adding a dependency would create a cycle."""

    def __init__(self, message: str, cycle_path: list[str] | None = None, path_str: str = "") -> None:
        super().__init__(message)
        self.cycle_path = cycle_path or []
        self.path_str = path_str


@dataclass
class CyclePreCheckResult:
    """Result of a fast cycle pre-check evaluation."""

    allowed: bool
    cycle_path: list[str] = field(default_factory=list)
    path_str: str = ""
    error: str = ""
    duration_ms: float = 0.0

    def __bool__(self) -> bool:
        return self.allowed

    def __iter__(self):
        yield self.allowed
        yield self.path_str


@dataclass
class DAGCachePayload:
    """Serializable in-memory representation of cached topology and reachability."""

    version: int = 1
    fingerprint: str = ""
    file_hashes: dict[str, str] = field(default_factory=dict)
    file_stats: dict[str, tuple[int, int]] = field(default_factory=dict)
    execution_tiers: dict[int, list[str]] = field(default_factory=dict)
    ordered_nodes: list[tuple[str, int]] = field(default_factory=list)
    critical_path_depth: int = 0
    adj: dict[str, list[str]] = field(default_factory=dict)
    reachability: dict[str, list[str]] = field(default_factory=dict)
    checksum: str = ""


def compute_content_sha256(content: str | bytes) -> str:
    raw = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(raw).hexdigest()


def normalize_task_id(tid: str) -> str:
    tid = tid.strip().upper()
    if tid.startswith("TASK-"):
        num_part = tid[5:]
        if num_part.isdigit():
            return f"TASK-{num_part.zfill(4)}"
        return tid
    if tid.isdigit():
        return f"TASK-{tid.zfill(4)}"
    return tid


def format_cycle_path(nodes: list[str]) -> list[str]:
    """Rotate elementary cycle path so it starts at the lexicographically lowest node."""
    if len(nodes) <= 1 or nodes[0] != nodes[-1]:
        return nodes
    unique = nodes[:-1]
    min_node = min(unique)
    min_idx = unique.index(min_node)
    return unique[min_idx:] + unique[:min_idx] + [min_node]


def bfs_shortest_path(adj: dict[str, list[str]], start: str, end: str) -> list[str]:
    """Finds shortest directed path from start to end using BFS."""
    if start == end:
        return [start]
    queue: deque[tuple[str, list[str]]] = deque([(start, [start])])
    visited: set[str] = {start}
    while queue:
        curr, path = queue.popleft()
        for nxt in sorted(adj.get(curr, [])):
            if nxt == end:
                return path + [end]
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, path + [nxt]))
    return [start, end]


def compute_reachability(adj: dict[str, list[str]], nodes: list[str]) -> dict[str, set[str]]:
    """Computes transitive reachability sets for all nodes."""
    reachability: dict[str, set[str]] = {}
    for node in nodes:
        visited: set[str] = set()
        queue: deque[str] = deque(adj.get(node, []))
        while queue:
            curr = queue.popleft()
            if curr not in visited:
                visited.add(curr)
                queue.extend(adj.get(curr, []))
        reachability[node] = visited
    return reachability


def can_add_dependency(
    cache: DAGCacheEngine | DAGCachePayload | dict[str, Any],
    source: str,
    target: str,
    raise_on_cycle: bool = False,
) -> CyclePreCheckResult:
    """Sub-5ms cycle pre-check using cached reachability sets."""
    t0 = time.perf_counter()
    src = normalize_task_id(source)
    tgt = normalize_task_id(target)

    adj: dict[str, list[str]] = {}
    reach: dict[str, set[str]] = {}

    if isinstance(cache, DAGCacheEngine):
        payload = cache.load_cache() or cache.build_cache()
        adj = payload.adj
        reach = {k: set(v) for k, v in payload.reachability.items()}
    elif isinstance(cache, DAGCachePayload):
        adj = cache.adj
        reach = {k: set(v) for k, v in cache.reachability.items()}
    elif isinstance(cache, dict):
        adj = cache.get("adj", {})
        reach = {k: set(v) for k, v in cache.get("reachability", {}).items()}

    # Self-loop
    if src == tgt:
        cycle = [src, src]
        p_str = f"{src} -> {src}"
        dur = (time.perf_counter() - t0) * 1000
        if raise_on_cycle:
            raise CyclicDependencyError(f"Cyclic dependency detected: {p_str}", cycle, p_str)
        return CyclePreCheckResult(
            allowed=False,
            cycle_path=cycle,
            path_str=p_str,
            error=f"Cyclic dependency detected: {p_str}",
            duration_ms=dur,
        )

    # If target reaches source, adding src -> tgt closes a cycle
    if src in reach.get(tgt, set()):
        path_from_target = bfs_shortest_path(adj, tgt, src)
        raw_cycle = [src] + path_from_target
        cycle = format_cycle_path(raw_cycle)
        p_str = " -> ".join(cycle)
        dur = (time.perf_counter() - t0) * 1000
        if raise_on_cycle:
            raise CyclicDependencyError(f"Cyclic dependency detected: {p_str}", cycle, p_str)
        return CyclePreCheckResult(
            allowed=False,
            cycle_path=cycle,
            path_str=p_str,
            error=f"Cyclic dependency detected: {p_str}",
            duration_ms=dur,
        )

    dur = (time.perf_counter() - t0) * 1000
    return CyclePreCheckResult(allowed=True, duration_ms=dur)


class DAGCacheEngine:
    """Incremental content-addressed topological cache engine for task DAGs."""

    def __init__(self, root_dir: Path | str) -> None:
        self.root_dir = Path(root_dir).resolve()
        self.backlog_dir = self.root_dir / "docs" / "project" / "backlog"
        self.cache_dir = self.root_dir / ".specops" / "cache"
        self.cache_file = self.cache_dir / "topology.json"
        self.last_hit: bool = False
        self._payload: DAGCachePayload | None = None

    def _discover_task_files(self) -> dict[str, Path]:
        tasks: dict[str, Path] = {}
        if not self.backlog_dir.exists():
            return tasks
        root_str = str(self.root_dir)
        p_len = len(root_str) + 1 if not root_str.endswith("/") else len(root_str)
        for folder in ("complete", "refined", "proposed"):
            target_folder = self.backlog_dir / folder
            if not target_folder.exists():
                continue
            for p in sorted(target_folder.glob("*.md")):
                if p.name.startswith(".") or not p.is_file() or p.name in ("PRIORITY.md", "ROADMAP.md", "README.md"):
                    continue
                rel = str(p)[p_len:]
                tasks[rel] = p
        return tasks

    def compute_backlog_fingerprint(
        self, files: dict[str, Path] | None = None
    ) -> tuple[str, dict[str, str], dict[str, tuple[int, int]]]:
        spec_files = files if files is not None else self._discover_task_files()
        hashes: dict[str, str] = {}
        stats: dict[str, tuple[int, int]] = {}
        for rel, path in sorted(spec_files.items()):
            try:
                st = path.stat()
                stats[rel] = (st.st_mtime_ns, st.st_size)
                hashes[rel] = compute_content_sha256(path.read_bytes())
            except OSError:
                continue
        combined = "\n".join(f"{k}:{v}" for k, v in sorted(hashes.items()))
        fingerprint = hashlib.sha256(combined.encode("utf-8")).hexdigest()
        return fingerprint, hashes, stats

    def is_cache_valid(self, payload: DAGCachePayload | None = None) -> bool:
        p = payload or self.load_cache()
        if p is None:
            return False
        current_files = self._discover_task_files()
        if set(current_files.keys()) != set(p.file_hashes.keys()):
            return False
        for rel, path in current_files.items():
            try:
                st = path.stat()
                cached_stat = p.file_stats.get(rel)
                if cached_stat and cached_stat == (st.st_mtime_ns, st.st_size):
                    continue
                if compute_content_sha256(path.read_bytes()) != p.file_hashes.get(rel):
                    return False
            except OSError:
                return False
        return True

    def load_cache(self) -> DAGCachePayload | None:
        if not self.cache_file.exists():
            return None
        try:
            raw = json.loads(self.cache_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("version") != 1:
                return None
            sub = {
                "fingerprint": raw.get("fingerprint", ""),
                "adj": raw.get("adj", {}),
                "reachability": raw.get("reachability", {}),
                "execution_tiers": raw.get("execution_tiers", {}),
            }
            expected_chk = hashlib.sha256(json.dumps(sub, sort_keys=True).encode("utf-8")).hexdigest()
            if raw.get("checksum") != expected_chk:
                return None
            tiers = {int(k): v for k, v in raw.get("execution_tiers", {}).items()}
            ordered = [(item[0], int(item[1])) for item in raw.get("ordered_nodes", [])]
            stats = {k: (int(v[0]), int(v[1])) for k, v in raw.get("file_stats", {}).items()}
            return DAGCachePayload(
                version=raw["version"],
                fingerprint=raw.get("fingerprint", ""),
                file_hashes=raw.get("file_hashes", {}),
                file_stats=stats,
                execution_tiers=tiers,
                ordered_nodes=ordered,
                critical_path_depth=raw.get("critical_path_depth", 0),
                adj=raw.get("adj", {}),
                reachability=raw.get("reachability", {}),
                checksum=raw.get("checksum", ""),
            )
        except Exception:
            return None

    def save_cache(self, payload: DAGCachePayload) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        raw_tiers = {str(k): v for k, v in payload.execution_tiers.items()}
        sub = {
            "fingerprint": payload.fingerprint,
            "adj": payload.adj,
            "reachability": payload.reachability,
            "execution_tiers": raw_tiers,
        }
        chk = hashlib.sha256(json.dumps(sub, sort_keys=True).encode("utf-8")).hexdigest()
        data = {
            "version": payload.version,
            "fingerprint": payload.fingerprint,
            "file_hashes": payload.file_hashes,
            "file_stats": {k: list(v) for k, v in payload.file_stats.items()},
            "execution_tiers": raw_tiers,
            "ordered_nodes": payload.ordered_nodes,
            "critical_path_depth": payload.critical_path_depth,
            "adj": payload.adj,
            "reachability": payload.reachability,
            "checksum": chk,
        }
        self.cache_file.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def build_cache(self, force: bool = False) -> DAGCachePayload:
        if not force:
            cached = self.load_cache()
            if cached and self.is_cache_valid(cached):
                self.last_hit = True
                self._payload = cached
                return cached

        self.last_hit = False
        files = self._discover_task_files()
        fp, hashes, stats = self.compute_backlog_fingerprint(files)

        adj: dict[str, list[str]] = {}
        all_nodes: set[str] = set()

        for rel, path in files.items():
            try:
                content = path.read_text(encoding="utf-8")
                meta, _ = extract_frontmatter(content)
                m = re.match(r"^(\d+)", path.stem)
                cid = f"TASK-{m.group(1).zfill(4)}" if m else meta.get("id", path.stem)
                canon_id = normalize_task_id(str(cid))
                all_nodes.add(canon_id)
                adj.setdefault(canon_id, [])

                raw_deps = meta.get("dependencies") or []
                if isinstance(raw_deps, str):
                    raw_deps = [d.strip() for d in raw_deps.strip("[]").split(",") if d.strip()]
                for dep in raw_deps:
                    clean = normalize_task_id(str(dep))
                    all_nodes.add(clean)
                    if clean not in adj[canon_id]:
                        adj[canon_id].append(clean)
                    adj.setdefault(clean, [])
            except Exception as e:
                logger.warning("Error parsing task file %s for DAG cache: %s", path, e)

        adj = {k: sorted(v) for k, v in sorted(adj.items())}
        nodes_list = sorted(all_nodes)

        tier_res = compute_execution_tiers(adj)
        reach = compute_reachability(adj, nodes_list)
        reach_serialized = {k: sorted(v) for k, v in sorted(reach.items())}

        payload = DAGCachePayload(
            version=1,
            fingerprint=fp,
            file_hashes=hashes,
            file_stats=stats,
            execution_tiers=tier_res.tiers,
            ordered_nodes=tier_res.ordered_nodes,
            critical_path_depth=tier_res.critical_path_depth,
            adj=adj,
            reachability=reach_serialized,
        )
        self.save_cache(payload)
        self._payload = payload
        return payload

    def get_execution_tiers(self, force: bool = False) -> dict[int, list[str]]:
        payload = self.build_cache(force=force)
        return payload.execution_tiers

    def can_add_dependency(self, source: str, target: str, raise_on_cycle: bool = False) -> CyclePreCheckResult:
        if self._payload is None or not self.is_cache_valid(self._payload):
            self.build_cache()
        return can_add_dependency(self._payload, source, target, raise_on_cycle=raise_on_cycle)
