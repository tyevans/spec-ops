"""Tests for architectural profiles and baseline ADR resolution."""

from pathlib import Path

from spec_ops.profiles.registry import list_profiles, resolve_adrs_for_profiles
from spec_ops.scaffold.init import init_project


def test_list_profiles():
    profiles = list_profiles()
    assert len(profiles) >= 3
    ids = [p.id for p in profiles]
    assert "core" in ids
    assert "bdd" in ids
    assert "ddd" in ids


def test_resolve_adrs_for_profiles():
    adrs = resolve_adrs_for_profiles(["core", "bdd"])
    assert len(adrs) == 6
    assert adrs[0].canonical_id == "ADR-0001"
    assert adrs[5].canonical_id == "ADR-0006"


def test_init_with_custom_profiles(tmp_path: Path):
    init_project(tmp_path, name="CustomProfileTest", profiles=["core"])
    adr_files = list((tmp_path / "docs" / "project" / "adrs" / "accepted").glob("*.md"))
    assert len(adr_files) == 5  # Only the 5 core ADRs

    registry_content = (tmp_path / "docs" / "project" / "adrs" / "REGISTRY.md").read_text(encoding="utf-8")
    assert "ADR-0001" in registry_content
    assert "ADR-0005" in registry_content
    assert "ADR-0006" not in registry_content
