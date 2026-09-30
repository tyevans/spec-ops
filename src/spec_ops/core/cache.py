"""Content-addressed SHA-256 relational graph caching engine."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import logging
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .graph import process_project_graph
from .models import ADR, PRD, Persona, ProjectData, Task, UserStory
from .parser import (
    parse_adr,
    parse_personas,
    parse_prd,
    parse_priority_ranks,
    parse_task,
    parse_user_story,
)

logger = logging.getLogger(__name__)


def compute_content_sha256(content: str | bytes) -> str:
    """Computes SHA-256 cryptographic digest of file contents."""
    raw = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(raw).hexdigest()


def compute_cache_checksum(payload: dict[str, Any]) -> str:
    """Computes deterministic checksum over cached entities and relational edges."""
    sub = {"entities": payload.get("entities", {}), "edges": payload.get("edges", [])}
    raw = json.dumps(sub, sort_keys=True).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


@dataclass
class CompileStats:
    """Runtime statistics for graph compilation."""

    cold: bool
    total_indexed: int
    invalidated: int
    cache_hits: int
    duration_ms: float = 0.0


@dataclass
class BenchmarkResult:
    """Synthetic benchmark results for graph compilation."""

    cold_seconds: float
    warm_seconds: float
    entities_count: int


def _serialize_entity(entity: Any) -> dict[str, Any]:
    d = dataclasses.asdict(entity)
    if d.get("file_path"):
        d["file_path"] = str(d["file_path"])
    return d


def _deserialize_entity(entity_type: str, data: dict[str, Any]) -> Any:
    d = dict(data)
    if d.get("file_path"):
        d["file_path"] = Path(d["file_path"])
    mapping = {"persona": Persona, "story": UserStory, "prd": PRD, "task": Task, "adr": ADR}
    cls = mapping.get(entity_type)
    if not cls:
        return None
    if entity_type == "task":
        d.pop("commits", None)
    return cls(**d)


def _build_cache_entry(
    rel: str, sha: str, etype: str, parsed: Any, st: Any = None
) -> tuple[Any, dict[str, Any]]:
    mtime = getattr(st, "st_mtime_ns", 0) if st else 0
    size = getattr(st, "st_size", 0) if st else 0
    if etype == "persona":
        plist = parsed if isinstance(parsed, list) else [parsed]
        return plist, {
            "rel_path": rel,
            "sha256": sha,
            "mtime_ns": mtime,
            "size": size,
            "entity_type": etype,
            "canonical_id": "personas",
            "data": [_serialize_entity(p) for p in plist],
            "dependencies": [],
            "dependents": [],
        }
    deps = (
        list(parsed.dependencies)
        + list(parsed.governing_prds)
        + list(parsed.governing_adrs)
        + list(parsed.governing_stories)
        if etype == "task"
        else ([parsed.governing_prd] if etype == "story" and parsed.governing_prd else [])
    )
    return parsed, {
        "rel_path": rel,
        "sha256": sha,
        "mtime_ns": mtime,
        "size": size,
        "entity_type": etype,
        "canonical_id": getattr(parsed, "canonical_id", parsed.id),
        "data": _serialize_entity(parsed),
        "dependencies": deps,
        "dependents": [],
    }


class RelationalGraphCacheEngine:
    """Incremental content-addressed SHA-256 relational graph cache engine."""

    def __init__(self, root_dir: Path):
        self.root_dir = root_dir.resolve()
        self.docs_dir = self.root_dir / "docs" / "project"
        self.cache_file = self.root_dir / ".specops" / "cache" / "graph.json"

    def load_cache(self) -> tuple[dict[str, Any] | None, bool]:
        """Loads and verifies graph cache from disk.

        Returns (cache_payload, was_corrupt).
        """
        if not self.cache_file.exists():
            return None, False
        try:
            raw = json.loads(self.cache_file.read_text(encoding="utf-8"))
            if not isinstance(raw, dict) or raw.get("checksum") != compute_cache_checksum(raw):
                raise ValueError("Corrupt or invalid checksum")
            return raw, False
        except Exception as exc:
            logger.warning(
                "Graph cache invalid: rebuilding index from source markdown (%s)", exc
            )
            return None, True

    def save_cache(self, cache_dict: dict[str, Any]) -> None:
        """Persists validated graph cache dictionary to disk with computed checksum."""
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_dict["checksum"] = compute_cache_checksum(cache_dict)
        self.cache_file.write_text(json.dumps(cache_dict), encoding="utf-8")

    def _discover_spec_files(self) -> dict[str, tuple[str, Path]]:
        found: dict[str, tuple[str, Path]] = {}
        if not self.docs_dir.exists():
            return found
        root_prefix = str(self.root_dir) + os.sep
        p_len = len(root_prefix)

        for dirpath, _, filenames in os.walk(str(self.docs_dir)):
            rel_dir = dirpath[p_len:]
            parts = rel_dir.split(os.sep)
            sub = parts[2] if len(parts) > 2 else ""
            etype = (
                "story"
                if sub == "user_stories"
                else (
                    "prd"
                    if sub == "product"
                    else ("adr" if sub == "adrs" else ("task" if sub == "backlog" else ""))
                )
            )

            for fn in filenames:
                if (
                    not fn.endswith(".md")
                    or fn.startswith(".")
                    or fn in ("REGISTRY.md", "FEATURE_INVENTORY.md", "README.md", "PRIORITY.md", "ROADMAP.md")
                ):
                    continue
                full_path = os.path.join(dirpath, fn)
                rel = full_path[p_len:]
                if fn == "PERSONAS.md":
                    found[rel] = ("persona", Path(full_path))
                elif etype:
                    found[rel] = (etype, Path(full_path))
        return found

    def _parse_entity_file(
        self, entity_type: str, file_path: Path, ranks: dict[str, int]
    ) -> Any:
        if entity_type == "persona":
            return parse_personas(file_path)
        if entity_type == "story":
            return parse_user_story(file_path)
        if entity_type == "prd":
            return parse_prd(file_path)
        if entity_type == "task":
            m = re.match(r"^(\d+)", file_path.stem)
            cid = f"TASK-{m.group(1).zfill(4)}" if m else file_path.stem
            return parse_task(file_path, priority_rank=ranks.get(cid, 999999))
        if entity_type == "adr":
            return parse_adr(file_path)
        return None

    def compile_graph(self, force_cold: bool = False) -> tuple[ProjectData, CompileStats]:
        """Compiles repository relational knowledge graph incrementally backed by SHA-256 cache."""
        t0 = time.perf_counter()
        spec_files = self._discover_spec_files()
        cached_payload, was_corrupt = self.load_cache()
        is_cold = force_cold or was_corrupt or cached_payload is None
        cached_entities = {} if is_cold else cached_payload.get("entities", {})

        current_hashes: dict[str, str] = {}
        file_stats: dict[str, Any] = {}
        for rel, (_, path) in spec_files.items():
            st = path.stat()
            file_stats[rel] = st
            old_e = cached_entities.get(rel)
            if (
                old_e
                and old_e.get("mtime_ns") == st.st_mtime_ns
                and old_e.get("size") == st.st_size
            ):
                current_hashes[rel] = old_e["sha256"]
            else:
                current_hashes[rel] = compute_content_sha256(path.read_bytes())

        if is_cold:
            invalidated_paths = set(spec_files.keys())
        else:
            id_to_rel = {
                ent["canonical_id"]: rel
                for rel, ent in cached_entities.items()
                if "canonical_id" in ent
            }
            modified = {
                rel
                for rel, ch in current_hashes.items()
                if cached_entities.get(rel, {}).get("sha256") != ch
            }
            invalidated_paths = set(modified)
            for rel in modified:
                old_ent = cached_entities.get(rel)
                if old_ent:
                    for dep_id in old_ent.get("dependents", []):
                        dep_rel = id_to_rel.get(dep_id)
                        if dep_rel and dep_rel in spec_files:
                            invalidated_paths.add(dep_rel)

        data = ProjectData()
        backlog_dir = self.docs_dir / "backlog"
        ranks = parse_priority_ranks(backlog_dir) if backlog_dir.exists() else {}
        cache_hits = 0
        updated_entities: dict[str, Any] = {}

        for rel, (etype, path) in spec_files.items():
            if rel not in invalidated_paths and rel in cached_entities:
                cache_hits += 1
                cdata = cached_entities[rel]["data"]
                if etype == "persona":
                    data.personas.extend([_deserialize_entity("persona", p) for p in cdata])
                else:
                    getattr(data, "stories" if etype == "story" else f"{etype}s").append(
                        _deserialize_entity(etype, cdata)
                    )
                updated_entities[rel] = cached_entities[rel]
            else:
                parsed = self._parse_entity_file(etype, path, ranks)
                ent_obj, centry = _build_cache_entry(
                    rel, current_hashes[rel], etype, parsed, st=file_stats.get(rel)
                )
                if etype == "persona":
                    data.personas.extend(ent_obj)
                else:
                    getattr(data, "stories" if etype == "story" else f"{etype}s").append(ent_obj)
                updated_entities[rel] = centry

        canon_map = {ent["canonical_id"]: ent for ent in updated_entities.values()}
        for e in updated_entities.values():
            e["dependents"] = []
        for e in updated_entities.values():
            cid = e["canonical_id"]
            for dep in e["dependencies"]:
                clean = dep.replace("TASK-", "").lstrip("0")
                canon = f"TASK-{clean.zfill(4)}" if clean and dep.startswith("TASK-") else dep
                target = canon_map.get(canon)
                if target and cid not in target["dependents"]:
                    target["dependents"].append(cid)

        process_project_graph(data)
        edges_serialized = [
            {
                "source_type": e.source_type,
                "source_id": e.source_id,
                "target_type": e.target_type,
                "target_id": e.target_id,
                "relation": e.relation,
            }
            for e in data.edges
        ]
        self.save_cache({"version": 1, "entities": updated_entities, "edges": edges_serialized})
        duration = (time.perf_counter() - t0) * 1000
        stats = CompileStats(
            cold=is_cold,
            total_indexed=len(updated_entities),
            invalidated=0 if is_cold else len(invalidated_paths),
            cache_hits=0 if is_cold else cache_hits,
            duration_ms=duration,
        )
        return data, stats


def benchmark_graph_compilation(
    num_entities: int = 1000, tmp_path: Path | None = None
) -> BenchmarkResult:
    """Benchmark helper to simulate cold and warm compilation runs."""
    import shutil
    import tempfile

    target_dir = tmp_path or Path(tempfile.mkdtemp(prefix="specops_bench_"))
    cleanup_needed = tmp_path is None

    try:
        p_docs = target_dir / "docs" / "project"
        p_personas = p_docs / "user_stories" / "PERSONAS.md"
        p_personas.parent.mkdir(parents=True, exist_ok=True)
        p_personas.write_text(
            "# Personas\n\n## 1. Alex - Architect\n- **Goals**: Speed\n", encoding="utf-8"
        )

        for sub in ("product/accepted", "user_stories/accepted", "backlog/refined", "adrs/accepted"):
            (p_docs / sub).mkdir(parents=True, exist_ok=True)

        n_prds, n_adrs, n_stories = 50, 50, 200
        n_tasks = num_entities - (1 + n_prds + n_adrs + n_stories)

        for i in range(1, n_prds + 1):
            (p_docs / "product" / "accepted" / f"prd-{i:04d}.md").write_text(
                f"---\nid: '{i:04d}'\ntitle: PRD {i}\nstatus: Accepted\n---\n## What the person cannot do today\nIssue\n",
                encoding="utf-8",
            )
        for i in range(1, n_adrs + 1):
            (p_docs / "adrs" / "accepted" / f"adr-{i:04d}.md").write_text(
                f"# ADR-{i:04d}: Arch Decision {i}\n\n## Context\nC\n## Decision\nD\n## Consequences\nE\n",
                encoding="utf-8",
            )
        for i in range(1, n_stories + 1):
            (p_docs / "user_stories" / "accepted" / f"us-{i:04d}.md").write_text(
                f"---\nid: '{i:04d}'\ntitle: Story {i}\nstatus: Accepted\ngoverning_prd: PRD-{(i % n_prds) + 1:04d}\npersona: Alex\n---\n**As an** arch\n**I want** speed\n**So that** rel\n",
                encoding="utf-8",
            )
        for i in range(1, n_tasks + 1):
            dep = f"[TASK-{max(1, i - 1):04d}]" if i > 1 else "[]"
            (p_docs / "backlog" / "refined" / f"{i:04d}-task.md").write_text(
                f"---\nid: '{i:04d}'\ntitle: Task {i}\nstatus: Refined\ndependencies: {dep}\n---\n# Task Details\n",
                encoding="utf-8",
            )

        engine = RelationalGraphCacheEngine(target_dir)
        t0 = time.perf_counter()
        _, stats = engine.compile_graph(force_cold=True)
        cold_time = time.perf_counter() - t0

        mod_task = p_docs / "backlog" / "refined" / f"{n_tasks:04d}-task.md"
        mod_task.write_text(
            f"---\nid: '{n_tasks:04d}'\ntitle: Task {n_tasks} Mod\nstatus: Refined\n---\n# Mod\n",
            encoding="utf-8",
        )

        t1 = time.perf_counter()
        engine.compile_graph()
        warm_time = time.perf_counter() - t1

        return BenchmarkResult(
            cold_seconds=cold_time, warm_seconds=warm_time, entities_count=stats.total_indexed
        )
    finally:
        if cleanup_needed:
            shutil.rmtree(target_dir, ignore_errors=True)
