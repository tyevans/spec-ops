"""Property-based generative tests for ADR supersession and cycle prevention (ADR-0009)."""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from spec_ops.adrs.supersede import (
    CircularSupersessionError,
    detect_supersession_cycles,
    discover_superseded_adrs,
    normalize_adr_id,
    supersede_adr,
)
from spec_ops.core.parser import extract_frontmatter


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    old_num=st.integers(min_value=1, max_value=50),
    new_num=st.integers(min_value=51, max_value=100),
    old_title=st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")), min_size=5, max_size=40),
    new_title=st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")), min_size=5, max_size=40),
)
def test_supersession_produces_bidirectional_cross_links(
    old_num: int,
    new_num: int,
    old_title: str,
    new_title: str,
):
    """Generative property test asserting that for any valid pair of ADRs, supersession

    produces bidirectional cross-links in frontmatter and REGISTRY.md (ADR-0009).
    """
    clean_old_title = " ".join(old_title.split()) or "Old Decision"
    clean_new_title = " ".join(new_title.split()) or "New Decision"

    old_id = f"ADR-{old_num:04d}"
    new_id = f"ADR-{new_num:04d}"

    with tempfile.TemporaryDirectory() as tmp_dir:
        docs_dir = Path(tmp_dir) / "docs" / "project"
        adrs_dir = docs_dir / "adrs"
        accepted_dir = adrs_dir / "accepted"
        proposed_dir = adrs_dir / "proposed"
        backlog_dir = docs_dir / "backlog"
        accepted_dir.mkdir(parents=True, exist_ok=True)
        proposed_dir.mkdir(parents=True, exist_ok=True)
        backlog_dir.mkdir(parents=True, exist_ok=True)

        old_file = accepted_dir / f"adr-{old_num:04d}-old.md"
        old_file.write_text(
            f"---\nid: '{old_num:04d}'\ntitle: '{clean_old_title}'\nstatus: Accepted\n---\n\n# {old_id}: {clean_old_title}\n\n## Status\nAccepted\n",
            encoding="utf-8",
        )

        new_file = proposed_dir / f"adr-{new_num:04d}-new.md"
        new_file.write_text(
            f"---\nid: '{new_num:04d}'\ntitle: '{clean_new_title}'\nstatus: Proposed\n---\n\n# {new_id}: {clean_new_title}\n\n## Status\nProposed\n",
            encoding="utf-8",
        )

        registry_file = adrs_dir / "REGISTRY.md"
        registry_file.write_text(
            f"# ADR Registry\n\n| ID | Title | Status | Date |\n|---|---|---|---|\n| {old_id} | {clean_old_title} | Accepted | 2026-09-29 |\n",
            encoding="utf-8",
        )

        res = supersede_adr(old_id, new_id, docs_dir)

        # 1. Assert Old ADR frontmatter and status
        old_meta, old_body = extract_frontmatter(res.old_file.read_text(encoding="utf-8"))
        assert old_meta.get("status") == "Superseded"
        assert old_meta.get("superseded_by") == new_id

        # 2. Assert New ADR frontmatter, status, and destination folder
        new_meta, new_body = extract_frontmatter(res.new_file.read_text(encoding="utf-8"))
        assert new_meta.get("status") == "Accepted"
        assert new_meta.get("supersedes") == old_id
        assert res.new_file.parent.name == "accepted"

        # 3. Assert REGISTRY.md table rows
        reg_content = registry_file.read_text(encoding="utf-8")
        assert f"| {old_id} | {clean_old_title} | Superseded (by {new_id}) |" in reg_content
        assert f"| {new_id} | {clean_new_title} | Accepted |" in reg_content

        # 4. Assert discovered mapping reflects active supersession
        discovered = discover_superseded_adrs(adrs_dir)
        assert discovered.get(old_id) == new_id


@settings(max_examples=30, deadline=None)
@given(
    chain_length=st.integers(min_value=1, max_value=8),
)
def test_circular_supersession_cycles_always_rejected(chain_length: int):
    """Generative property test asserting that circular supersession cycles of any length

    (including self-supersession and N-step transitive loops) are always rejected (ADR-0009).
    """
    if chain_length == 1:
        # Self-supersession: ADR-0001 -> ADR-0001
        with pytest.raises(CircularSupersessionError):
            detect_supersession_cycles({}, ("ADR-0001", "ADR-0001"))
        return

    # Create a linear supersession chain: ADR-0001 -> ADR-0002 -> ... -> ADR-000N
    existing_map: dict[str, str] = {}
    for i in range(1, chain_length):
        existing_map[f"ADR-{i:04d}"] = f"ADR-{i+1:04d}"

    # Now attempt to close the cycle: ADR-000N -> ADR-0001
    closing_pair = (f"ADR-{chain_length:04d}", "ADR-0001")
    with pytest.raises(CircularSupersessionError) as exc_info:
        detect_supersession_cycles(existing_map, closing_pair)

    assert "Circular ADR supersession detected" in str(exc_info.value)
