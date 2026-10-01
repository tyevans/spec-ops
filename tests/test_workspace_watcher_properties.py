"""Hypothesis generative property invariant tests for incremental graph invalidation.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009, ADR-0015; PRD-0005; US-0059.
Asserts that for any arbitrary sequence of file change events, the incremental
graph cache state exactly matches the state produced by a cold full-compilation from scratch.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.core.cache import RelationalGraphCacheEngine, compute_cache_checksum
from spec_ops.graph.workspace_watcher import IncrementalGraphInvalidator
from spec_ops.scaffold.init import init_project


def _scaffold_base_repo(root: Path) -> None:
    init_project(root, name="HypothesisWatcherRepo")
    docs = root / "docs" / "project"
    (docs / "product" / "accepted").mkdir(parents=True, exist_ok=True)
    (docs / "user_stories" / "accepted").mkdir(parents=True, exist_ok=True)
    (docs / "backlog" / "refined").mkdir(parents=True, exist_ok=True)
    (docs / "adrs" / "accepted").mkdir(parents=True, exist_ok=True)
    (root / "src").mkdir(parents=True, exist_ok=True)

    (docs / "user_stories" / "PERSONAS.md").write_text(
        "# Personas\n\n## 1. Alex — Architect\n- **Role**: Architect\n- **Pain Points**: Drift\n",
        encoding="utf-8",
    )
    (docs / "product" / "accepted" / "prd-0001-core.md").write_text(
        "---\nid: '0001'\ntitle: Core Platform PRD\nstatus: Accepted\n---\n## Checkable Outcomes\n1. Deterministic\n",
        encoding="utf-8",
    )
    (docs / "adrs" / "accepted" / "adr-0001-arch.md").write_text(
        "# ADR-0001: Architecture\n\n## Status\nAccepted\n## Context\nContext\n## Decision\nDecide\n## Consequences\nGood\n",
        encoding="utf-8",
    )
    (docs / "user_stories" / "accepted" / "us-0001-engine.md").write_text(
        "---\nid: '0001'\ntitle: Engine Story\nstatus: Accepted\npersona: Alex\ngoverning_prd: PRD-0001\n---\nStory details\n",
        encoding="utf-8",
    )
    (docs / "backlog" / "refined" / "TASK-0001.md").write_text(
        "---\nid: '0001'\ntitle: Task 1 Title\nstatus: Refined\ndependencies: []\ngoverning_adrs: [ADR-0001]\ngoverning_prds: [PRD-0001]\ngoverning_stories: [US-0001]\n---\n# Task 1\n",
        encoding="utf-8",
    )
    (docs / "backlog" / "refined" / "TASK-0002.md").write_text(
        "---\nid: '0002'\ntitle: Task 2 Title\nstatus: Refined\ndependencies: [TASK-0001]\ngoverning_adrs: [ADR-0001]\ngoverning_prds: [PRD-0001]\n---\n# Task 2\n",
        encoding="utf-8",
    )


action_strategy = st.tuples(
    st.sampled_from(["modify_task_1", "modify_task_2", "add_task_3", "modify_prd", "modify_adr", "delete_task_2"]),
    st.text(min_size=1, max_size=30, alphabet="abcdefghijklmnopqrstuvwxyz0123456789 _-"),
)


@settings(max_examples=25, deadline=None)
@given(actions=st.lists(action_strategy, min_size=1, max_size=8))
def test_incremental_graph_matches_cold_compilation(actions: list[tuple[str, str]]) -> None:
    """Property: For any arbitrary sequence of file change events, incremental graph state matches cold compilation."""
    temp_dir = Path(tempfile.mkdtemp(prefix="hypothesis_watcher_"))
    try:
        _scaffold_base_repo(temp_dir)
        invalidator = IncrementalGraphInvalidator(temp_dir)
        invalidator.load_cache()

        docs = temp_dir / "docs" / "project"

        for action, payload in actions:
            clean_str = payload.replace("\n", " ").strip() or "updated"
            if action == "modify_task_1":
                p = docs / "backlog" / "refined" / "TASK-0001.md"
                p.write_text(
                    f"---\nid: '0001'\ntitle: Task 1 {clean_str}\nstatus: Refined\ndependencies: []\ngoverning_adrs: [ADR-0001]\ngoverning_prds: [PRD-0001]\n---\n# Content {clean_str}\n",
                    encoding="utf-8",
                )
                invalidator.invalidate_file(p)
            elif action == "modify_task_2":
                p = docs / "backlog" / "refined" / "TASK-0002.md"
                if p.exists():
                    p.write_text(
                        f"---\nid: '0002'\ntitle: Task 2 {clean_str}\nstatus: Refined\ndependencies: [TASK-0001]\ngoverning_adrs: [ADR-0001]\n---\n# Content {clean_str}\n",
                        encoding="utf-8",
                    )
                    invalidator.invalidate_file(p)
            elif action == "add_task_3":
                p = docs / "backlog" / "refined" / "TASK-0003.md"
                p.write_text(
                    f"---\nid: '0003'\ntitle: Task 3 {clean_str}\nstatus: Refined\ndependencies: [TASK-0001]\ngoverning_adrs: [ADR-0001]\n---\n# Content {clean_str}\n",
                    encoding="utf-8",
                )
                invalidator.invalidate_file(p)
            elif action == "modify_prd":
                p = docs / "product" / "accepted" / "prd-0001-core.md"
                p.write_text(
                    f"---\nid: '0001'\ntitle: Core Platform {clean_str}\nstatus: Accepted\n---\n## Checkable Outcomes\n1. Fast {clean_str}\n",
                    encoding="utf-8",
                )
                invalidator.invalidate_file(p)
            elif action == "modify_adr":
                p = docs / "adrs" / "accepted" / "adr-0001-arch.md"
                p.write_text(
                    f"# ADR-0001: Architecture {clean_str}\n\n## Status\nAccepted\n## Context\n{clean_str}\n## Decision\nDecide\n## Consequences\nGood\n",
                    encoding="utf-8",
                )
                invalidator.invalidate_file(p)
            elif action == "delete_task_2":
                p = docs / "backlog" / "refined" / "TASK-0002.md"
                if p.exists():
                    p.unlink()
                    invalidator.invalidate_file(p)

        # 1. Capture incremental cache state
        cache_file = temp_dir / ".specops" / "cache" / "graph.json"
        assert cache_file.exists()
        inc_cache = json.loads(cache_file.read_text(encoding="utf-8"))

        # 2. Run cold compilation from scratch on identical filesystem state
        cold_engine = RelationalGraphCacheEngine(temp_dir)
        cold_engine.compile_graph(force_cold=True)
        cold_cache = json.loads(cache_file.read_text(encoding="utf-8"))

        # 3. Assert entity sets match
        assert set(inc_cache["entities"].keys()) == set(cold_cache["entities"].keys())

        # 4. Assert each entity matches canonical_id, sha256, entity_type, and dependencies
        for rel_path, inc_ent in inc_cache["entities"].items():
            cold_ent = cold_cache["entities"][rel_path]
            assert inc_ent["canonical_id"] == cold_ent["canonical_id"]
            assert inc_ent["sha256"] == cold_ent["sha256"]
            assert inc_ent["entity_type"] == cold_ent["entity_type"]
            assert inc_ent["dependencies"] == cold_ent["dependencies"]
            if inc_ent["entity_type"] == "persona":
                assert inc_ent["data"] == cold_ent["data"]
            else:
                assert inc_ent["data"]["title"] == cold_ent["data"]["title"]

        # 5. Assert edges match
        inc_edges = {(e["source_id"], e["target_id"], e["relation"]) for e in inc_cache.get("edges", [])}
        cold_edges = {(e["source_id"], e["target_id"], e["relation"]) for e in cold_cache.get("edges", [])}
        assert inc_edges == cold_edges

        # 6. Assert checksums match
        assert inc_cache["checksum"] == cold_cache["checksum"]

    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
