"""Unit tests for semantic profile diff calculation and formatting engine."""

from __future__ import annotations

import json
from spec_ops.profiles.diff import (
    ADRDiff,
    ConfigDiff,
    InvariantDiff,
    ProfileSemanticDiff,
    compute_profile_diff,
)
from spec_ops.profiles.models import BaselineADR, Profile


def test_compute_profile_diff_basic_addition():
    adr1 = BaselineADR(number=1, slug="spec-as-code", title="Spec as Code", content="content 1")
    adr2 = BaselineADR(number=2, slug="frontdoors", title="Frontdoors", content="content 2")

    prof_a = Profile(id="core", name="Core", description="", version="1.0.0", adrs=[adr1])
    prof_b = Profile(id="core", name="Core", description="", version="2.0.0", adrs=[adr1, adr2])

    diff = compute_profile_diff(prof_a, prof_b)
    assert diff.source_id == "core"
    assert diff.source_version == "1.0.0"
    assert diff.target_id == "core"
    assert diff.target_version == "2.0.0"
    assert len(diff.adrs) == 1
    assert diff.adrs[0].change_type == "added"
    assert diff.adrs[0].slug == "frontdoors"
    assert diff.adrs[0].target_title == "Frontdoors"
    assert not diff.is_breaking


def test_compute_profile_diff_modified_adr():
    adr1_v1 = BaselineADR(number=1, slug="spec", title="Spec Old", content="Old body")
    adr1_v2 = BaselineADR(number=1, slug="spec", title="Spec New", content="New body")

    prof_a = Profile(id="core", name="Core", description="", version="1.0.0", adrs=[adr1_v1])
    prof_b = Profile(id="core", name="Core", description="", version="2.0.0", adrs=[adr1_v2])

    diff = compute_profile_diff(prof_a, prof_b)
    assert len(diff.adrs) == 1
    assert diff.adrs[0].change_type == "modified"
    assert diff.adrs[0].source_title == "Spec Old"
    assert diff.adrs[0].target_title == "Spec New"
    assert diff.adrs[0].content_changed is True


def test_compute_profile_diff_modified_adr_title_only():
    adr1_v1 = BaselineADR(number=1, slug="spec", title="Spec Old", content="Same body")
    adr1_v2 = BaselineADR(number=1, slug="spec", title="Spec New", content="Same body")

    prof_a = Profile(id="core", name="Core", description="", version="1.0.0", adrs=[adr1_v1])
    prof_b = Profile(id="core", name="Core", description="", version="2.0.0", adrs=[adr1_v2])

    diff = compute_profile_diff(prof_a, prof_b)
    assert len(diff.adrs) == 1
    assert diff.adrs[0].change_type == "modified"
    assert diff.adrs[0].source_title == "Spec Old"
    assert diff.adrs[0].target_title == "Spec New"
    assert diff.adrs[0].content_changed is False


def test_compute_profile_diff_extraction_fallbacks():
    from spec_ops.profiles.diff import _extract_file_limit, _extract_mutation_testing

    class DummyWithLimit:
        file_length_limit = 420

    assert _extract_file_limit(DummyWithLimit()) == 420

    class DummyInvalidLimit:
        overrides = {"architecture": {"file_length_limit": "invalid_number"}}

    assert _extract_file_limit(DummyInvalidLimit()) == 500

    class DummyEmptyOverrides:
        overrides = "not a dict"

    assert _extract_file_limit(DummyEmptyOverrides()) == 500
    assert _extract_mutation_testing(DummyEmptyOverrides()) is False

    class DummyWithMutation:
        overrides = {"quality": {"require_mutation_testing": True}}

    assert _extract_mutation_testing(DummyWithMutation()) is True


def test_compute_profile_diff_composition_objects():
    from spec_ops.profiles.composer import ResolvedComposition

    comp_a = ResolvedComposition(profile_ids=["base"], adrs=[], file_length_limit=500, version="1.0")
    comp_b = ResolvedComposition(profile_ids=["custom"], adrs=[], file_length_limit=350, version="2.0")

    diff = compute_profile_diff(comp_a, comp_b)
    assert diff.source_id == "base"
    assert diff.target_id == "custom"
    assert diff.is_breaking is True


def test_compute_profile_diff_removed_adr_is_breaking():
    adr1 = BaselineADR(number=1, slug="spec", title="Spec", content="Body 1")
    adr2 = BaselineADR(number=2, slug="legacy", title="Legacy ADR", content="Body 2")

    prof_a = Profile(id="core", name="Core", description="", version="1.0.0", adrs=[adr1, adr2])
    prof_b = Profile(id="core", name="Core", description="", version="2.0.0", adrs=[adr1])

    diff = compute_profile_diff(prof_a, prof_b)
    assert len(diff.adrs) == 1
    assert diff.adrs[0].change_type == "removed"
    assert diff.adrs[0].slug == "legacy"
    assert diff.is_breaking is True
    assert any("Deprecated/removed" in bc for bc in diff.breaking_changes)


def test_compute_profile_diff_invariants():
    prof_a = Profile(id="core", name="Core", description="", version="1.0.0", invariants=["Rule A", "Rule B"])
    prof_b = Profile(id="core", name="Core", description="", version="2.0.0", invariants=["Rule B", "Rule C"])

    diff = compute_profile_diff(prof_a, prof_b)
    assert diff.invariants.added == ["Rule C"]
    assert diff.invariants.removed == ["Rule A"]


def test_compute_profile_diff_decreased_file_limit_breaking():
    prof_a = Profile(
        id="core",
        name="Core",
        description="",
        version="1.0.0",
        overrides={"architecture": {"file_length_limit": 500}},
    )
    prof_b = Profile(
        id="core",
        name="Core",
        description="",
        version="2.0.0",
        overrides={"architecture": {"file_length_limit": 350}},
    )

    diff = compute_profile_diff(prof_a, prof_b)
    assert diff.config.file_length_limit == (500, 350)
    assert diff.is_breaking is True
    assert any("Decreased file length limit from 500 to 350" in bc for bc in diff.breaking_changes)


def test_compute_profile_diff_increased_file_limit_not_breaking():
    prof_a = Profile(
        id="core",
        name="Core",
        description="",
        version="1.0.0",
        overrides={"architecture": {"file_length_limit": 300}},
    )
    prof_b = Profile(
        id="core",
        name="Core",
        description="",
        version="2.0.0",
        overrides={"architecture": {"file_length_limit": 500}},
    )

    diff = compute_profile_diff(prof_a, prof_b)
    assert diff.config.file_length_limit == (300, 500)
    assert diff.is_breaking is False


def test_compute_profile_diff_mandated_mutation_testing_breaking():
    prof_a = Profile(
        id="core",
        name="Core",
        description="",
        version="1.0.0",
        overrides={"quality": {"require_mutation_testing": False}},
    )
    prof_b = Profile(
        id="core",
        name="Core",
        description="",
        version="2.0.0",
        overrides={"quality": {"require_mutation_testing": True}},
    )

    diff = compute_profile_diff(prof_a, prof_b)
    assert diff.config.require_mutation_testing == (False, True)
    assert diff.is_breaking is True
    assert any("Newly mandated mutation testing" in bc for bc in diff.breaking_changes)


def test_render_text_and_to_dict():
    adr1 = BaselineADR(number=1, slug="spec", title="Spec", content="Old body")
    adr2 = BaselineADR(number=2, slug="addon", title="Addon", content="New body")

    prof_a = Profile(
        id="core",
        name="Core",
        description="",
        version="1.0.0",
        adrs=[adr1],
        invariants=["Old Invariant"],
        overrides={"architecture": {"file_length_limit": 500}},
    )
    prof_b = Profile(
        id="core",
        name="Core",
        description="",
        version="2.0.0",
        adrs=[adr1, adr2],
        invariants=["Old Invariant", "New Invariant"],
        overrides={"architecture": {"file_length_limit": 350}, "quality": {"require_mutation_testing": True}},
    )

    diff = compute_profile_diff(prof_a, prof_b)
    text = diff.render_text()
    assert "=== SpecOps Profile Semantic Diff: core@1.0.0 -> core@2.0.0 ===" in text
    assert "⚠️  BREAKING CHANGES (2):" in text
    assert "Decreased file length limit" in text
    assert "Newly mandated mutation testing" in text
    assert "+ Added ADR-0002: Addon" in text
    assert "+ Added: New Invariant" in text
    assert "file_length_limit: 500 -> 350" in text
    assert "quality.require_mutation_testing: false -> true" in text

    # to_dict
    d = diff.to_dict()
    assert d["source"] == "core@1.0.0"
    assert d["target"] == "core@2.0.0"
    assert d["is_breaking"] is True
    assert len(d["breaking_changes"]) == 2
    assert len(d["adrs"]) == 1
    assert d["adrs"][0]["change_type"] == "added"
    assert d["invariants"]["added"] == ["New Invariant"]
    assert d["configuration"]["file_length_limit"] == {"source": 500, "target": 350}
    assert d["configuration"]["require_mutation_testing"] == {"source": False, "target": True}

    # JSON serializable
    json_str = json.dumps(d)
    assert "core@2.0.0" in json_str


def test_render_text_no_changes():
    prof = Profile(id="core", name="Core", description="", version="1.0.0")
    diff = compute_profile_diff(prof, prof)
    text = diff.render_text()
    assert "=== SpecOps Profile Semantic Diff: core@1.0.0 -> core@1.0.0 ===" in text
    assert "(no changes)" in text
    assert not diff.is_breaking


def test_cli_profile_diff_specops_base(tmp_path, monkeypatch, capsys):
    import sys
    from spec_ops.cli.main import main

    monkeypatch.chdir(tmp_path)
    (tmp_path / "specops.toml").write_text('[project]\nname = "test"\n[profiles]\ninstalled = ["specops/base@v1.0"]\nversion = "1.0"\n', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["spec-ops", "profile", "diff", "specops/base@v2.0"])
    ret = main()
    assert ret == 0
    captured = capsys.readouterr()
    assert "SpecOps Profile Semantic Diff" in captured.out
    assert "ADR-0008" in captured.out
    assert "BREAKING CHANGES" in captured.out


def test_cli_profile_diff_json(tmp_path, monkeypatch, capsys):
    import sys
    from spec_ops.cli.main import main

    monkeypatch.chdir(tmp_path)
    (tmp_path / "specops.toml").write_text('[project]\nname = "test"\n[profiles]\ninstalled = ["core@1.0.0"]\n', encoding="utf-8")
    monkeypatch.setattr(sys, "argv", ["spec-ops", "profile", "diff", "core", "--json"])
    ret = main()
    assert ret == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["source"] == "core@1.0.0"
    assert data["target"] == "core@2.0.0"
    assert data["is_breaking"] is True


def test_cli_profile_upgrade_no_arg(tmp_path, monkeypatch, capsys):
    import sys
    from spec_ops.cli.main import main
    from spec_ops.profiles.registry import CORE_ADR_0001

    monkeypatch.chdir(tmp_path)
    adrs_dir = tmp_path / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True)
    (adrs_dir / "adr-0001-spec.md").write_text(CORE_ADR_0001.content, encoding="utf-8")
    (tmp_path / "docs" / "project" / "adrs" / "REGISTRY.md").write_text("# Registry\n", encoding="utf-8")
    (tmp_path / "specops.toml").write_text('[project]\nname = "test"\n[profiles]\ninstalled = ["core@1.0.0"]\n', encoding="utf-8")

    monkeypatch.setattr(sys, "argv", ["spec-ops", "profile", "upgrade"])
    ret = main()
    assert ret == 0
    captured = capsys.readouterr()
    assert "Profile upgraded cleanly to core@2.0.0" in captured.out
    toml_text = (tmp_path / "specops.toml").read_text(encoding="utf-8")
    assert "core@2.0.0" in toml_text


