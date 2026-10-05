"""Property-based generative tests for ADR amendments and cycle prevention (ADR-0009)."""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from spec_ops.adrs.amend import (
    CircularAmendmentError,
    detect_amendment_cycles,
    discover_amended_adrs,
)
from spec_ops.adrs.amendment import ADRAmendmentEngine
from spec_ops.adrs.supersede import normalize_adr_id
from spec_ops.core.parser import extract_frontmatter


@settings(max_examples=25, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    old_num=st.integers(min_value=1, max_value=50),
    new_num=st.integers(min_value=51, max_value=100),
    old_title=st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")), min_size=5, max_size=40),
    new_title=st.text(alphabet=st.characters(whitelist_categories=("Lu", "Ll", "Nd", "Zs")), min_size=5, max_size=40),
)
def test_amendment_produces_bidirectional_lineage_and_preserves_accepted_status(
    old_num: int,
    new_num: int,
    old_title: str,
    new_title: str,
):
    """Asserts that for any pair of ADRs, amendment generates bidirectional lineage (amends/amended_by)

    and maintains Accepted status for the predecessor decision (ADR-0009).
    """
    clean_old_title = " ".join(old_title.split()) or "Foundation Decision"
    clean_new_title = " ".join(new_title.split()) or "Amendment Decision"

    old_id = f"ADR-{old_num:04d}"
    new_id = f"ADR-{new_num:04d}"

    with tempfile.TemporaryDirectory() as tmp_dir:
        root_dir = Path(tmp_dir)
        adrs_dir = root_dir / "docs" / "project" / "adrs"
        accepted_dir = adrs_dir / "accepted"
        accepted_dir.mkdir(parents=True, exist_ok=True)

        old_file = accepted_dir / f"adr-{old_num:04d}-base.md"
        old_file.write_text(
            f"---\nid: '{old_num:04d}'\ntitle: '{clean_old_title}'\nstatus: Accepted\n---\n\n# {old_id}: {clean_old_title}\n\n## Status\nAccepted\n",
            encoding="utf-8",
        )

        registry_file = adrs_dir / "REGISTRY.md"
        registry_file.write_text(
            f"| {old_id} | {clean_old_title} | Accepted | 2026-01-01 |\n",
            encoding="utf-8",
        )

        engine = ADRAmendmentEngine(root_dir=root_dir)
        res = engine.amend(old_target=old_id, title=clean_new_title)

        assert res.old_id == old_id
        assert res.new_id == "ADR-0051" or res.new_id.startswith("ADR-")

        # Verify old ADR maintains Accepted status and records amended_by
        old_meta, _ = extract_frontmatter(old_file.read_text(encoding="utf-8"))
        assert old_meta.get("status") in ("Accepted", "Accepted (Amended)")
        assert res.new_id in [normalize_adr_id(str(x)) for x in old_meta.get("amended_by", [])]

        # Verify new ADR records amends and is Accepted
        new_meta, _ = extract_frontmatter(res.new_file.read_text(encoding="utf-8"))
        assert new_meta.get("status") == "Accepted"
        assert old_id in [normalize_adr_id(str(x)) for x in new_meta.get("amends", [])]


@settings(max_examples=30, deadline=None)
@given(
    chain_length=st.integers(min_value=2, max_value=8),
)
def test_circular_amendment_detection_property(chain_length: int):
    """Property test verifying that circular amendment chains of any length are detected and rejected."""
    adrs = [f"ADR-{i:04d}" for i in range(1, chain_length + 1)]

    # Linear chain: ADR-0002 amends ADR-0001, ADR-0003 amends ADR-0002, etc.
    existing_map: dict[str, list[str]] = {}
    for i in range(1, chain_length):
        existing_map[adrs[i]] = [adrs[i - 1]]

    # Closing the loop: ADR-0001 amends ADR-000N must fail
    with pytest.raises(CircularAmendmentError):
        detect_amendment_cycles(existing_map, (adrs[0], adrs[-1]))
