"""Generative property tests for EventBus and InMemoryGraphState isomorphism.

Governed by ADR-0009 (Hypothesis Invariant Property: Event Replay Isomorphism).
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from hypothesis import given, settings, strategies as st

from spec_ops.core.cache import RelationalGraphCacheEngine
from spec_ops.core.event_bus import EventBus, InMemoryGraphState


@st.composite
def graph_mutation_sequence(draw: st.DrawFn) -> list[dict[str, Any]]:
    """Generates an arbitrary sequence of graph mutation operations."""
    num_ops = draw(st.integers(min_value=3, max_value=8))
    ops: list[dict[str, Any]] = []

    for _ in range(num_ops):
        op_type = draw(st.sampled_from(["add_prd", "add_adr", "add_story", "add_task", "change_task_status"]))
        idx = draw(st.integers(min_value=1, max_value=5))
        if op_type == "add_prd":
            ops.append({"type": "add_prd", "id": f"PRD-{idx:04d}"})
        elif op_type == "add_adr":
            ops.append({"type": "add_adr", "id": f"ADR-{idx:04d}"})
        elif op_type == "add_story":
            prd_idx = draw(st.integers(min_value=1, max_value=5))
            ops.append({"type": "add_story", "id": f"US-{idx:04d}", "prd": f"PRD-{prd_idx:04d}"})
        elif op_type == "add_task":
            dep_idx = draw(st.integers(min_value=1, max_value=5))
            dep = f"TASK-{dep_idx:04d}" if dep_idx != idx else None
            status = draw(st.sampled_from(["Proposed", "Refined"]))
            ops.append({
                "type": "add_task",
                "id": f"TASK-{idx:04d}",
                "status": status,
                "dep": dep,
            })
        elif op_type == "change_task_status":
            new_status = draw(st.sampled_from(["Proposed", "Refined"]))
            ops.append({"type": "change_task_status", "id": f"TASK-{idx:04d}", "status": new_status})

    return ops


@settings(max_examples=30, deadline=5000)
@given(graph_mutation_sequence())
def test_event_replay_isomorphism(mutations: list[dict[str, Any]]) -> None:
    """Asserts that real-time in-memory graph state is isomorphic to cold graph compilation."""
    temp_dir = Path(tempfile.mkdtemp(prefix="specops_iso_"))
    try:
        p_docs = temp_dir / "docs" / "project"
        (p_docs / "product" / "accepted").mkdir(parents=True, exist_ok=True)
        (p_docs / "adrs" / "accepted").mkdir(parents=True, exist_ok=True)
        (p_docs / "user_stories" / "accepted").mkdir(parents=True, exist_ok=True)
        (p_docs / "backlog" / "proposed").mkdir(parents=True, exist_ok=True)
        (p_docs / "backlog" / "refined").mkdir(parents=True, exist_ok=True)

        bus = EventBus()
        in_memory_state = InMemoryGraphState(temp_dir)
        in_memory_state.load_initial_state()

        for op in mutations:
            op_type = op["type"]
            target_path: Path | None = None

            if op_type == "add_prd":
                clean_id = op["id"].split("-")[-1]
                target_path = p_docs / "product" / "accepted" / f"prd-{clean_id}.md"
                target_path.write_text(f"---\nid: '{clean_id}'\ntitle: PRD {clean_id}\nstatus: Accepted\n---\n", encoding="utf-8")
            elif op_type == "add_adr":
                clean_id = op["id"].split("-")[-1]
                target_path = p_docs / "adrs" / "accepted" / f"adr-{clean_id}.md"
                target_path.write_text(f"# {op['id']}: Arch Decision {clean_id}\n\n## Status\nAccepted\n", encoding="utf-8")
            elif op_type == "add_story":
                clean_id = op["id"].split("-")[-1]
                target_path = p_docs / "user_stories" / "accepted" / f"us-{clean_id}.md"
                target_path.write_text(f"---\nid: '{clean_id}'\ntitle: Story {clean_id}\ngoverning_prd: {op['prd']}\n---\n", encoding="utf-8")
            elif op_type in ("add_task", "change_task_status"):
                clean_id = op["id"].split("-")[-1]
                sub = "refined" if op["status"] == "Refined" else "proposed"
                other_sub = "proposed" if sub == "refined" else "refined"
                old_other_file = p_docs / "backlog" / other_sub / f"{clean_id}-task.md"
                new_file = p_docs / "backlog" / sub / f"{clean_id}-task.md"

                if old_other_file.exists():
                    old_other_file.unlink()
                    in_memory_state.apply_file_changes([old_other_file], event_bus=bus)

                deps_yaml = f"dependencies:\n  - {op['dep']}\n" if op.get("dep") else ""
                new_file.write_text(f"---\nid: '{clean_id}'\ntitle: Task {clean_id}\nstatus: {op['status']}\n{deps_yaml}---\n", encoding="utf-8")
                target_path = new_file

            if target_path is not None:
                in_memory_state.apply_file_changes([target_path], event_bus=bus)

        # Cold re-parse
        engine = RelationalGraphCacheEngine(temp_dir)
        cold_data, _ = engine.compile_graph(force_cold=True)

        # Invariant Assertions: Event Replay Isomorphism
        in_mem_tasks = {t.canonical_id: t.status for t in in_memory_state.project_data.tasks}
        cold_tasks = {t.canonical_id: t.status for t in cold_data.tasks}
        assert in_mem_tasks == cold_tasks

        in_mem_stories = sorted(s.id for s in in_memory_state.project_data.stories)
        cold_stories = sorted(s.id for s in cold_data.stories)
        assert in_mem_stories == cold_stories

        in_mem_prds = sorted(p.id for p in in_memory_state.project_data.prds)
        cold_prds = sorted(p.id for p in cold_data.prds)
        assert in_mem_prds == cold_prds

        in_mem_adrs = sorted(a.id for a in in_memory_state.project_data.adrs)
        cold_adrs = sorted(a.id for a in cold_data.adrs)
        assert in_mem_adrs == cold_adrs

        in_mem_edges = sorted((e.source_id, e.target_id, e.relation) for e in in_memory_state.project_data.edges)
        cold_edges = sorted((e.source_id, e.target_id, e.relation) for e in cold_data.edges)
        assert in_mem_edges == cold_edges
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
