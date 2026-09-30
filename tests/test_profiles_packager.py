"""Unit tests for profile packaging, distribution bundles, and installation engine."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from spec_ops.profiles.models import ProfileError
from spec_ops.profiles.packager import (
    install_profile_bundle,
    load_profile_from_bundle,
    package_profile,
    validate_profile_source,
)


def test_validate_profile_source_success(tmp_path: Path):
    prof_dir = tmp_path / "valid_profile"
    prof_dir.mkdir()
    (prof_dir / "profile.toml").write_text(
        """[profile]
id = "fintech"
name = "Fintech Profile"
version = "1.0.0"

[overrides.architecture]
file_length_limit = 350

[invariants]
rules = ["Audit rule"]
""",
        encoding="utf-8",
    )
    adrs_dir = prof_dir / "adrs"
    adrs_dir.mkdir()
    (adrs_dir / "adr-0010-custom.md").write_text(
        "---\nid: '0010'\ntitle: Custom ADR\nstatus: Accepted\n---\n# ADR-0010: Custom ADR\n",
        encoding="utf-8",
    )

    is_valid, errors = validate_profile_source(prof_dir)
    assert is_valid is True
    assert errors == []


def test_validate_profile_source_failures(tmp_path: Path):
    prof_dir = tmp_path / "bad_profile"
    prof_dir.mkdir()

    # Missing profile.toml
    is_valid, errors = validate_profile_source(prof_dir)
    assert is_valid is False
    assert any("Missing 'profile.toml'" in e for e in errors)

    # Invalid TOML
    (prof_dir / "profile.toml").write_text("[invalid toml", encoding="utf-8")
    is_valid, errors = validate_profile_source(prof_dir)
    assert is_valid is False
    assert any("Invalid TOML" in e for e in errors)

    # Negative file length limit & empty rules
    (prof_dir / "profile.toml").write_text(
        """[profile]
id = "bad"

[overrides.architecture]
file_length_limit = -10

[invariants]
rules = [""]
""",
        encoding="utf-8",
    )
    is_valid, errors = validate_profile_source(prof_dir)
    assert is_valid is False
    assert any("positive integer" in e for e in errors)
    assert any("non-empty strings" in e for e in errors)


def test_package_and_load_bundle(tmp_path: Path):
    prof_dir = tmp_path / "src_prof"
    prof_dir.mkdir()
    (prof_dir / "profile.toml").write_text(
        """[profile]
id = "custom_bundle"
name = "Custom Bundle"
version = "2.1.0"
extends = ["core"]
""",
        encoding="utf-8",
    )
    (prof_dir / "adr-0009-something.md").write_text(
        "---\nid: '0009'\ntitle: Something\nstatus: Accepted\n---\n# ADR-0009: Something\n",
        encoding="utf-8",
    )

    out_sop = tmp_path / "dist" / "custom_bundle.sop"
    created = package_profile(prof_dir, out_sop)
    assert created.is_file()

    loaded = load_profile_from_bundle(created)
    assert loaded.id == "custom_bundle"
    assert loaded.version == "2.1.0"
    assert len(loaded.adrs) == 1
    assert loaded.adrs[0].canonical_id == "ADR-0009"


def test_package_builtin_profile(tmp_path: Path):
    out_tar = tmp_path / "dist" / "core_bundle.tar.gz"
    created = package_profile("core", out_tar)
    assert created.is_file()

    loaded = load_profile_from_bundle(created)
    assert loaded.id == "core"
    assert len(loaded.adrs) == 5


def test_package_invalid_profile_raises(tmp_path: Path):
    with pytest.raises(ProfileError):
        package_profile("completely_unknown_profile", tmp_path / "dist.sop")


def test_install_profile_bundle(tmp_path: Path):
    # Setup target repo
    from spec_ops.scaffold.init import init_project

    repo = tmp_path / "repo"
    init_project(repo, name="BundleInstallTest", profiles=["core"])

    # Create bundle
    prof_dir = tmp_path / "addon_prof"
    prof_dir.mkdir()
    (prof_dir / "profile.toml").write_text(
        """[profile]
id = "addon-profile"
name = "Addon Profile"
version = "1.0.0"
extends = ["core"]

[overrides.architecture]
file_length_limit = 380

[overrides.quality]
require_mutation_testing = true

[invariants]
rules = ["Mandatory Addon Invariant"]
""",
        encoding="utf-8",
    )
    (prof_dir / "adr-0010-addon.md").write_text(
        "---\nid: '0010'\ntitle: Addon Architecture\nstatus: Accepted\n---\n# ADR-0010: Addon Architecture\n",
        encoding="utf-8",
    )
    bundle_path = tmp_path / "addon.sop"
    package_profile(prof_dir, bundle_path)

    # Install bundle into target repo
    installed_prof = install_profile_bundle(bundle_path, repo)
    assert installed_prof.id == "addon-profile"

    # Verify ADRs installed
    adrs_accepted = repo / "docs" / "project" / "adrs" / "accepted"
    adr_files = [f.name for f in adrs_accepted.glob("*.md")]
    assert any("addon" in name for name in adr_files)

    # Verify REGISTRY.md
    reg_content = (repo / "docs" / "project" / "adrs" / "REGISTRY.md").read_text(encoding="utf-8")
    assert "Addon Architecture" in reg_content

    # Verify specops.toml
    toml_content = (repo / "specops.toml").read_text(encoding="utf-8")
    assert "file_length_limit = 380" in toml_content
    assert "addon-profile" in toml_content
    assert "require_mutation_testing = true" in toml_content

    # Verify AGENTS.md
    agents_content = (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert "<380 lines" in agents_content
    assert "Mandatory Addon Invariant" in agents_content


def test_cli_profile_export_and_inspect(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    from spec_ops.cli.main import main

    # 1. Export core profile
    bundle_dest = tmp_path / "dist" / "core.tar.gz"
    monkeypatch.setattr(sys, "argv", ["spec-ops", "profile", "export", "core", "--output", str(bundle_dest)])
    ret = main()
    assert ret == 0
    assert bundle_dest.is_file()

    # 2. Inspect core profile
    monkeypatch.setattr(sys, "argv", ["spec-ops", "profile", "inspect", "core"])
    ret = main()
    assert ret == 0
    captured = capsys.readouterr()
    assert "=== SpecOps Profile Inspection: core ===" in captured.out
    assert "ADR-0001" in captured.out


def test_cli_profile_inspect_cycle_fails(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    from spec_ops.cli.main import main

    pa_dir = tmp_path / "profiles" / "pa"
    pb_dir = tmp_path / "profiles" / "pb"
    pa_dir.mkdir(parents=True)
    pb_dir.mkdir(parents=True)
    (pa_dir / "profile.toml").write_text('[profile]\nid = "pa"\nextends = ["pb"]\n')
    (pb_dir / "profile.toml").write_text('[profile]\nid = "pb"\nextends = ["pa"]\n')

    monkeypatch.setattr(sys, "argv", ["spec-ops", "profile", "inspect", str(pa_dir)])
    ret = main()
    assert ret == 1
    captured = capsys.readouterr()
    assert "Circular dependency detected" in captured.err
