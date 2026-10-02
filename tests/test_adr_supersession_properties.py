"""Hypothesis generative property tests for ADR Supersession and Evolution Engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, ADR-0009; PRD-0005; TASK-0165.
"""

from __future__ import annotations

from pathlib import Path
import tempfile
from hypothesis import given, settings
import hypothesis.strategies as st

from spec_ops.adrs.supersede import detect_supersession_cycles
from spec_ops.adrs.supersession import ADRSupersessionEngine, find_next_adr_id


@settings(max_examples=50, deadline=None)
@given(
    titles=st.lists(
        st.text(
            alphabet=st.characters(whitelist_categories=["Lu", "Ll", "Nd", "Zs"]),
            min_size=1,
            max_size=30,
        ).filter(lambda s: bool(s.strip())),
        min_size=1,
        max_size=6,
    )
)
def test_sequential_supersessions_form_acyclic_lineage(titles: list[str]):
    """Asserts that sequential supersessions produce a strict DAG with unique IDs and no cycles."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        root_dir = Path(tmp_dir)
        engine = ADRSupersessionEngine(root_dir=root_dir)
        adrs_dir = engine.get_adrs_dir()
        accepted_dir = adrs_dir / "accepted"
        accepted_dir.mkdir(parents=True, exist_ok=True)

        # Create root initial ADR
        root_adr = accepted_dir / "adr-0001-root.md"
        root_adr.write_text(
            """---
id: ADR-0001
title: Root Decision
status: Accepted
date: 2026-01-01
---
# ADR-0001: Root Decision
""",
            encoding="utf-8",
        )

        current_target = "ADR-0001"
        lineage_map: dict[str, str] = {}
        all_ids = {"ADR-0001"}

        for i, title in enumerate(titles, start=2):
            res = engine.supersede(old_target=current_target, title=title)
            expected_id = f"ADR-{i:04d}"
            assert res.new_id == expected_id
            assert res.old_id == current_target
            assert res.new_file.exists()
            assert res.old_file.exists()

            # Record lineage
            lineage_map[res.old_id] = res.new_id
            all_ids.add(res.new_id)
            current_target = res.new_id

        # Invariant 1: All generated IDs are unique
        assert len(all_ids) == len(titles) + 1

        # Invariant 2: Lineage contains zero circular cycles
        detect_supersession_cycles(lineage_map)

        # Invariant 3: Next ID correctly reflects the total count
        next_id, next_num = find_next_adr_id(adrs_dir)
        assert next_num == len(titles) + 2
        assert next_id == f"ADR-{next_num:04d}"
