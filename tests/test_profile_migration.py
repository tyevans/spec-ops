"""Unit tests for profile migration engine and 3-way conflict resolution."""

from __future__ import annotations

from pathlib import Path

from spec_ops.profiles.migration import (
    detect_adr_conflicts,
    execute_profile_migration,
    find_installed_adr_file,
    render_conflict_prompt,
)
from spec_ops.profiles.models import BaselineADR, Profile


def _setup_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir(parents=True, exist_ok=True)
    adrs_dir = repo / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)

    (adrs_dir / "adr-0001-spec-as-code.md").write_text(
        "# ADR-0001: Spec as Code\n\nOriginal content.\n",
        encoding="utf-8",
    )
    (adrs_dir / "adr-0002-file-limits.md").write_text(
        "# ADR-0002: File Limits\n\n500 lines limit.\n",
        encoding="utf-8",
    )

    (repo / "docs" / "project" / "adrs" / "REGISTRY.md").write_text(
        "# ADR Registry\n\n| ID | Title | Status | Date |\n|---|---|---|---|\n| ADR-0001 | Spec as Code | Accepted | 2026-09-29 |\n| ADR-0002 | File Limits | Accepted | 2026-09-29 |\n",
        encoding="utf-8",
    )

    (repo / "specops.toml").write_text(
        '[project]\nname = "test-repo"\n\n[architecture]\nfile_length_limit = 500\n\n[profiles]\ninstalled = ["core@1.0.0"]\nversion = "1.0.0"\n',
        encoding="utf-8",
    )

    (repo / "AGENTS.md").write_text(
        "# Constitution\n1. **File Length Limit (<500 lines)**:\nSource files over ~500 lines are forbidden.\n",
        encoding="utf-8",
    )

    return repo


def test_find_installed_adr_file(tmp_path: Path):
    repo = _setup_repo(tmp_path)
    adrs_dir = repo / "docs" / "project" / "adrs" / "accepted"
    p = find_installed_adr_file(adrs_dir, "file-limits", 2)
    assert p is not None
    assert p.name == "adr-0002-file-limits.md"


def test_detect_conflict_when_local_modified(tmp_path: Path):
    repo = _setup_repo(tmp_path)
    adrs_dir = repo / "docs" / "project" / "adrs" / "accepted"

    # Local modification
    (adrs_dir / "adr-0002-file-limits.md").write_text(
        "# ADR-0002: File Limits\n\nLocal override: 600 lines.\n",
        encoding="utf-8",
    )

    base_adr2 = BaselineADR(number=2, slug="file-limits", title="File Limits", content="# ADR-0002: File Limits\n\n500 lines limit.\n")
    base_prof = Profile(id="core", name="Core", description="", version="1.0.0", adrs=[base_adr2])

    up_adr2 = BaselineADR(number=2, slug="file-limits", title="File Limits", content="# ADR-0002: File Limits\n\nUpstream tightened: 350 lines.\n")
    up_prof = Profile(id="core", name="Core", description="", version="2.0.0", adrs=[up_adr2])

    conflicts = detect_adr_conflicts(up_prof, repo, base_profile=base_prof)
    assert len(conflicts) == 1
    assert conflicts[0].canonical_id == "ADR-0002"
    assert "Local override: 600 lines" in conflicts[0].local_content
    assert "Upstream tightened: 350 lines" in conflicts[0].upstream_content
    prompt = render_conflict_prompt(conflicts[0])
    assert "Conflict detected for ADR-0002" in prompt
    assert "keep-local" in prompt


def test_safe_abort_preserves_state_verbatim(tmp_path: Path):
    repo = _setup_repo(tmp_path)
    adrs_dir = repo / "docs" / "project" / "adrs" / "accepted"

    # Local modification to trigger conflict
    adr2_file = adrs_dir / "adr-0002-file-limits.md"
    original_adr2 = "# ADR-0002: File Limits\n\nLocal override: 600 lines.\n"
    adr2_file.write_text(original_adr2, encoding="utf-8")

    original_specops = (repo / "specops.toml").read_text(encoding="utf-8")
    original_agents = (repo / "AGENTS.md").read_text(encoding="utf-8")
    original_registry = (repo / "docs" / "project" / "adrs" / "REGISTRY.md").read_text(encoding="utf-8")

    base_adr2 = BaselineADR(number=2, slug="file-limits", title="File Limits", content="# ADR-0002: File Limits\n\n500 lines limit.\n")
    base_prof = Profile(id="core", name="Core", description="", version="1.0.0", adrs=[base_adr2])

    up_adr2 = BaselineADR(number=2, slug="file-limits", title="File Limits", content="# ADR-0002: File Limits\n\nUpstream tightened: 350 lines.\n")
    up_adr3 = BaselineADR(number=3, slug="new-rule", title="New Rule", content="# ADR-0003: New Rule\n")
    up_prof = Profile(id="core", name="Core", description="", version="2.0.0", adrs=[up_adr2, up_adr3])

    res = execute_profile_migration(up_prof, repo, base_profile=base_prof, action="abort")
    assert res.success is False
    assert res.aborted is True
    assert len(res.conflicts) == 1

    # Verify state preserved verbatim
    assert adr2_file.read_text(encoding="utf-8") == original_adr2
    assert (repo / "specops.toml").read_text(encoding="utf-8") == original_specops
    assert (repo / "AGENTS.md").read_text(encoding="utf-8") == original_agents
    assert (repo / "docs" / "project" / "adrs" / "REGISTRY.md").read_text(encoding="utf-8") == original_registry
    assert not (adrs_dir / "adr-0003-new-rule.md").exists()


def test_upgrade_clean_application_and_adr_addition(tmp_path: Path):
    repo = _setup_repo(tmp_path)
    adrs_dir = repo / "docs" / "project" / "adrs" / "accepted"

    base_adr1 = BaselineADR(number=1, slug="spec-as-code", title="Spec as Code", content="# ADR-0001: Spec as Code\n\nOriginal content.\n")
    base_adr2 = BaselineADR(number=2, slug="file-limits", title="File Limits", content="# ADR-0002: File Limits\n\n500 lines limit.\n")
    base_prof = Profile(id="core", name="Core", description="", version="1.0.0", adrs=[base_adr1, base_adr2])

    up_adr1 = BaselineADR(number=1, slug="spec-as-code", title="Spec as Code", content="# ADR-0001: Spec as Code\n\nUpstream refined.\n")
    up_adr2 = BaselineADR(number=2, slug="file-limits", title="File Limits", content="# ADR-0002: File Limits\n\n500 lines limit.\n")
    up_adr8 = BaselineADR(number=8, slug="testing", title="Testing Gate", content="# ADR-0008: Testing Gate\n\nMandate mutation tests.\n")

    up_prof = Profile(
        id="core",
        name="Core",
        description="",
        version="2.0.0",
        adrs=[up_adr1, up_adr2, up_adr8],
        overrides={"architecture": {"file_length_limit": 350}, "quality": {"require_mutation_testing": True}},
        invariants=["Mandatory mutation tests"],
    )

    res = execute_profile_migration(up_prof, repo, base_profile=base_prof)
    assert res.success is True
    assert res.aborted is False

    # ADR-0001 should be updated (non-conflicting amendment)
    adr1_content = (adrs_dir / "adr-0001-spec-as-code.md").read_text(encoding="utf-8")
    assert "Upstream refined." in adr1_content

    # ADR-0003 (installed sequentially for ADR-0008) should exist
    new_files = [f.name for f in adrs_dir.glob("*.md")]
    assert any("testing" in f for f in new_files)

    # REGISTRY.md should be updated
    reg_text = (repo / "docs" / "project" / "adrs" / "REGISTRY.md").read_text(encoding="utf-8")
    assert "Testing Gate" in reg_text

    # specops.toml should be updated
    toml_text = (repo / "specops.toml").read_text(encoding="utf-8")
    assert "core@2.0.0" in toml_text
    assert "version = \"2.0.0\"" in toml_text
    assert "file_length_limit = 350" in toml_text
    assert "require_mutation_testing = true" in toml_text

    # AGENTS.md should be updated
    agents_text = (repo / "AGENTS.md").read_text(encoding="utf-8")
    assert "<350 lines" in agents_text
    assert "Mandatory mutation tests" in agents_text


def test_upgrade_keep_local_resolution(tmp_path: Path):
    repo = _setup_repo(tmp_path)
    adrs_dir = repo / "docs" / "project" / "adrs" / "accepted"

    # Local modification
    adr2_file = adrs_dir / "adr-0002-file-limits.md"
    adr2_file.write_text("# ADR-0002: File Limits\n\nLocal override.\n", encoding="utf-8")

    base_adr2 = BaselineADR(number=2, slug="file-limits", title="File Limits", content="# ADR-0002: File Limits\n\n500 lines limit.\n")
    base_prof = Profile(id="core", name="Core", description="", version="1.0.0", adrs=[base_adr2])

    up_adr2 = BaselineADR(number=2, slug="file-limits", title="File Limits", content="# ADR-0002: File Limits\n\nUpstream 350.\n")
    up_prof = Profile(id="core", name="Core", description="", version="2.0.0", adrs=[up_adr2])

    res = execute_profile_migration(up_prof, repo, base_profile=base_prof, action="keep-local")
    assert res.success is True
    # Local content preserved
    assert "Local override." in adr2_file.read_text(encoding="utf-8")


def test_upgrade_force_resolution(tmp_path: Path):
    repo = _setup_repo(tmp_path)
    adrs_dir = repo / "docs" / "project" / "adrs" / "accepted"

    adr2_file = adrs_dir / "adr-0002-file-limits.md"
    adr2_file.write_text("# ADR-0002: File Limits\n\nLocal override.\n", encoding="utf-8")

    base_adr2 = BaselineADR(number=2, slug="file-limits", title="File Limits", content="# ADR-0002: File Limits\n\n500 lines limit.\n")
    base_prof = Profile(id="core", name="Core", description="", version="1.0.0", adrs=[base_adr2])

    up_adr2 = BaselineADR(number=2, slug="file-limits", title="File Limits", content="# ADR-0002: File Limits\n\nUpstream 350.\n")
    up_prof = Profile(id="core", name="Core", description="", version="2.0.0", adrs=[up_adr2])

    res = execute_profile_migration(up_prof, repo, base_profile=base_prof, force=True)
    assert res.success is True
    assert "Upstream 350." in adr2_file.read_text(encoding="utf-8")
