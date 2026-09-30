"""Unit tests for constitution_sync.py to maximize mutmut mutant kill rate."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from spec_ops.scaffold.constitution_sync import (
    BEGIN_CUSTOM_INVARIANTS,
    END_CUSTOM_INVARIANTS,
    check_constitution,
    extract_custom_invariants,
    generate_expected_constitution,
    inject_custom_invariants,
    sync_constitution,
    wrap_custom_invariants,
)
from spec_ops.scaffold.init import init_project


def test_constants():
    assert BEGIN_CUSTOM_INVARIANTS == "<!-- BEGIN CUSTOM INVARIANTS -->"
    assert END_CUSTOM_INVARIANTS == "<!-- END CUSTOM INVARIANTS -->"


def test_extract_custom_invariants_missing_begin():
    assert extract_custom_invariants("No markers here") is None
    assert extract_custom_invariants(f"Only end {END_CUSTOM_INVARIANTS}") is None


def test_extract_custom_invariants_missing_end():
    content = f"{BEGIN_CUSTOM_INVARIANTS} unterminated custom block"
    assert extract_custom_invariants(content) is None


def test_extract_custom_invariants_exact():
    content = f"Header\n{BEGIN_CUSTOM_INVARIANTS}My Custom Rule\nLine 2{END_CUSTOM_INVARIANTS}\nFooter"
    extracted = extract_custom_invariants(content)
    assert extracted == "My Custom Rule\nLine 2"


def test_extract_custom_invariants_empty():
    content = f"{BEGIN_CUSTOM_INVARIANTS}{END_CUSTOM_INVARIANTS}"
    assert extract_custom_invariants(content) == ""


def test_wrap_custom_invariants():
    assert wrap_custom_invariants(None) == f"{BEGIN_CUSTOM_INVARIANTS}\n{END_CUSTOM_INVARIANTS}"
    assert wrap_custom_invariants("") == f"{BEGIN_CUSTOM_INVARIANTS}{END_CUSTOM_INVARIANTS}"
    assert wrap_custom_invariants("hello") == f"{BEGIN_CUSTOM_INVARIANTS}hello{END_CUSTOM_INVARIANTS}"


def test_inject_custom_invariants_existing_block():
    doc = f"Start\n{BEGIN_CUSTOM_INVARIANTS}old{END_CUSTOM_INVARIANTS}\nEnd"
    res = inject_custom_invariants(doc, "new")
    assert res == f"Start\n{BEGIN_CUSTOM_INVARIANTS}new{END_CUSTOM_INVARIANTS}\nEnd"


def test_inject_custom_invariants_before_design_principles():
    doc = "# Title\n\n## Hard Invariants\nRule 1\n\n## Design Principles\nPrinciple 1\n"
    res = inject_custom_invariants(doc, "custom")
    assert f"{BEGIN_CUSTOM_INVARIANTS}custom{END_CUSTOM_INVARIANTS}" in res
    assert "## Design Principles\nPrinciple 1" in res


def test_inject_custom_invariants_fallback_append():
    doc = "# Title\nNo design principles here."
    res = inject_custom_invariants(doc, "custom")
    expected = f"{doc}\n\n{BEGIN_CUSTOM_INVARIANTS}custom{END_CUSTOM_INVARIANTS}\n"
    assert res == expected


def test_inject_custom_invariants_with_none():
    doc = f"Start\n{BEGIN_CUSTOM_INVARIANTS}old{END_CUSTOM_INVARIANTS}\nEnd"
    res = inject_custom_invariants(doc, None)
    assert res == f"Start\n{BEGIN_CUSTOM_INVARIANTS}\n{END_CUSTOM_INVARIANTS}\nEnd"


def test_check_constitution_missing_file(tmp_path: Path):
    in_sync, diff, msg = check_constitution(tmp_path)
    assert in_sync is False
    assert diff == "AGENTS.md does not exist."
    assert "Constitution Drift Error" in msg


def test_check_constitution_synced(tmp_path: Path):
    init_project(name="SyncedApp", target_dir=tmp_path)
    # Sync first
    ok, _ = sync_constitution(tmp_path)
    assert ok is True

    in_sync, diff, msg = check_constitution(tmp_path)
    assert in_sync is True
    assert diff == ""
    assert "✅ AGENTS.md is synchronized with configuration." in msg


def test_check_constitution_drifted(tmp_path: Path):
    init_project(name="DriftedApp", target_dir=tmp_path)
    sync_constitution(tmp_path)

    # Change AGENTS.md directly
    agents_path = tmp_path / "AGENTS.md"
    content = agents_path.read_text(encoding="utf-8")
    agents_path.write_text(content.replace("File Length Limit", "Altered Limit"), encoding="utf-8")

    in_sync, diff, msg = check_constitution(tmp_path)
    assert in_sync is False
    assert "--- AGENTS.md (actual)" in diff
    assert "+++ AGENTS.md (expected)" in diff
    assert "Constitution Drift Error: AGENTS.md is out of sync with specops.toml. Run 'spec-ops scaffold agents' to update." in msg


def test_sync_constitution_creates_files(tmp_path: Path):
    init_project(name="SyncCreateApp", target_dir=tmp_path)
    (tmp_path / "AGENTS.md").unlink()
    manual = tmp_path / "docs" / "operating-manual.md"
    if manual.exists():
        manual.unlink()

    ok, msg = sync_constitution(tmp_path)
    assert ok is True
    assert "updated successfully" in msg
    assert (tmp_path / "AGENTS.md").is_file()
    assert (tmp_path / "docs" / "operating-manual.md").is_file()


def test_generate_expected_constitution_security_detection(tmp_path: Path):
    init_project(name="SecTestApp", target_dir=tmp_path)
    # With SECURITY.md
    sec_md = tmp_path / "docs" / "project" / "SECURITY.md"
    sec_md.parent.mkdir(parents=True, exist_ok=True)
    sec_md.write_text("# Security Policy\n", encoding="utf-8")

    res = generate_expected_constitution(tmp_path)
    assert "Security & Supply-Chain Hard Invariants" in res


def test_generate_expected_constitution_security_in_toml(tmp_path: Path):
    init_project(name="SecTomlApp", target_dir=tmp_path)
    # Remove security from config object and SECURITY.md
    sec_md = tmp_path / "docs" / "project" / "SECURITY.md"
    if sec_md.exists():
        sec_md.unlink()
    toml_path = tmp_path / "specops.toml"
    content = toml_path.read_text(encoding="utf-8")
    if "[security]" not in content:
        toml_path.write_text(content + "\n[security]\nsecret_scanning = true\n", encoding="utf-8")

    res = generate_expected_constitution(tmp_path)
    assert "Security & Supply-Chain Hard Invariants" in res


def test_sync_constitution_git_trailers(tmp_path: Path):
    repo = tmp_path / "git_repo"
    repo.mkdir()
    init_project(name="GitTrailersApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@specops.dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True, capture_output=True)

    with patch("spec_ops.adrs.supersede.discover_superseded_adrs", return_value={"ADR-0003": "ADR-0015"}):
        ok, msg = sync_constitution(repo)
        assert ok is True

    # Check git log for trailer
    log = subprocess.run(["git", "log", "-n", "1"], cwd=repo, capture_output=True, text=True).stdout
    assert "SpecOps-ADR: ADR-0015" in log


def test_discover_superseded_exception_handled(tmp_path: Path):
    init_project(name="ExcApp", target_dir=tmp_path)
    with patch("spec_ops.adrs.supersede.discover_superseded_adrs", side_effect=RuntimeError("Discovery error")):
        res = generate_expected_constitution(tmp_path)
        assert "Hard Invariants" in res
        ok, msg = sync_constitution(tmp_path)
        assert ok is True


def test_git_commit_exception_handled(tmp_path: Path):
    repo = tmp_path / "git_fail"
    repo.mkdir()
    init_project(name="GitFailApp", target_dir=repo)
    (repo / ".git").mkdir()

    with patch("spec_ops.adrs.supersede.discover_superseded_adrs", return_value={"ADR-0003": "ADR-0015"}):
        with patch("subprocess.run", side_effect=subprocess.SubprocessError("git error")):
            ok, msg = sync_constitution(repo)
            assert ok is True

