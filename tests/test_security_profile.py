"""Unit tests for the security architectural profile, policy validation, and guardrails."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from spec_ops.config.loader import load_config
from spec_ops.profiles.registry import get_profile, list_profiles, resolve_adrs_for_profiles
from spec_ops.profiles.security import (
    CONFIG_RESTORATION_GUIDANCE,
    DEFAULT_SECURITY_MD,
    DEFAULT_SECURITY_TOML,
    REQUIRED_POLICY_MARKERS,
    SECURITY_PROFILE,
    SECURITY_RESTORATION_GUIDANCE,
    apply_security_profile,
    install_security_adrs,
    scaffold_security_policy,
    sync_security_profile,
    validate_security_policy,
)
from spec_ops.scaffold.agents_md import scaffold_agents_command
from spec_ops.scaffold.init import init_project

SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
CLI_ENV = {**os.environ, "PYTHONPATH": f"{SRC_DIR}:{os.environ.get('PYTHONPATH', '')}".rstrip(":")}


def test_security_profile_registered():
    profile = get_profile("security")
    assert profile is not None
    assert profile.id == "security"
    assert len(profile.adrs) == 3
    slugs = [a.slug for a in profile.adrs]
    assert "zero-trust-worker-process-sandboxing" in slugs
    assert "immutable-supply-chain-lockfile-enforcement" in slugs
    assert "secret-scanning-and-credential-leak-defense" in slugs


def test_resolve_adrs_with_security():
    adrs = resolve_adrs_for_profiles(["core", "bdd", "ddd", "security"])
    assert len(adrs) == 10
    canonical_ids = [a.canonical_id for a in adrs]
    assert canonical_ids == [f"ADR-{i:04d}" for i in range(1, 11)]
    assert "ADR-0010" in canonical_ids


def test_validate_security_policy_missing_file(tmp_path: Path):
    ok, msg = validate_security_policy(tmp_path)
    assert not ok
    assert msg == SECURITY_RESTORATION_GUIDANCE


def test_validate_security_policy_empty_file(tmp_path: Path):
    sec_md = tmp_path / "docs" / "project" / "SECURITY.md"
    sec_md.parent.mkdir(parents=True, exist_ok=True)
    sec_md.write_text("# Too short\n", encoding="utf-8")
    ok, msg = validate_security_policy(tmp_path)
    assert not ok
    assert msg == SECURITY_RESTORATION_GUIDANCE


def test_validate_security_policy_missing_markers(tmp_path: Path):
    sec_md = tmp_path / "docs" / "project" / "SECURITY.md"
    sec_md.parent.mkdir(parents=True, exist_ok=True)
    sec_md.write_text(
        "# Some Long Policy\n\nThis is a long policy that omits the required marker keywords completely.\n" * 5,
        encoding="utf-8",
    )
    ok, msg = validate_security_policy(tmp_path)
    assert not ok
    assert msg == SECURITY_RESTORATION_GUIDANCE


def test_validate_security_policy_missing_toml_section(tmp_path: Path):
    sec_md = tmp_path / "docs" / "project" / "SECURITY.md"
    sec_md.parent.mkdir(parents=True, exist_ok=True)
    sec_md.write_text(DEFAULT_SECURITY_MD, encoding="utf-8")

    toml_path = tmp_path / "specops.toml"
    toml_path.write_text('[project]\nname = "NoSec"\n', encoding="utf-8")

    ok, msg = validate_security_policy(tmp_path)
    assert not ok
    assert msg == CONFIG_RESTORATION_GUIDANCE


def test_validate_security_policy_length_boundaries(tmp_path: Path):
    sec_md = tmp_path / "docs" / "project" / "SECURITY.md"
    sec_md.parent.mkdir(parents=True, exist_ok=True)
    # 49 chars -> too short
    sec_md.write_text("a" * 49, encoding="utf-8")
    ok, msg = validate_security_policy(tmp_path)
    assert not ok
    assert msg == SECURITY_RESTORATION_GUIDANCE

    # 50 chars with markers
    marker_text = "Vulnerability Disclosure Reporting Contacts PGP Fingerprint"
    assert len(marker_text) >= 50
    sec_md.write_text(marker_text, encoding="utf-8")
    ok, msg = validate_security_policy(tmp_path)
    assert ok


def test_validate_security_policy_individual_missing_markers(tmp_path: Path):
    sec_md = tmp_path / "docs" / "project" / "SECURITY.md"
    sec_md.parent.mkdir(parents=True, exist_ok=True)

    base = "Vulnerability Disclosure\nReporting Contacts\nPGP Fingerprint\n" + ("padding line\n" * 5)
    for marker in REQUIRED_POLICY_MARKERS:
        modified = base.replace(marker, "omitted")
        sec_md.write_text(modified, encoding="utf-8")
        ok, msg = validate_security_policy(tmp_path)
        assert not ok
        assert msg == SECURITY_RESTORATION_GUIDANCE


def test_validate_security_policy_read_error(tmp_path: Path):
    sec_md = tmp_path / "docs" / "project" / "SECURITY.md"
    sec_md.parent.mkdir(parents=True, exist_ok=True)
    # Create directory instead of file to trigger OSError on read_text
    # Wait: sec_md.is_file() will be False. To trigger OSError inside read_text, make it unreadable
    sec_md.write_text(DEFAULT_SECURITY_MD, encoding="utf-8")
    sec_md.chmod(0o000)
    try:
        ok, msg = validate_security_policy(tmp_path)
        assert not ok
        assert msg == SECURITY_RESTORATION_GUIDANCE
    finally:
        sec_md.chmod(0o644)


def test_install_security_adrs_comprehensive(tmp_path: Path):
    docs_adrs = tmp_path / "docs" / "project" / "adrs"
    docs_adrs.mkdir(parents=True, exist_ok=True)
    registry_file = docs_adrs / "REGISTRY.md"
    registry_file.write_text("# Registry\n\n| ID | Title | Status | Date |\n|---|---|---|---|\n", encoding="utf-8")

    # Install from scratch
    installed = install_security_adrs(tmp_path)
    assert len(installed) == 3
    assert installed[0].name == "adr-0001-zero-trust-worker-process-sandboxing.md"
    assert installed[1].name == "adr-0002-immutable-supply-chain-lockfile-enforcement.md"
    assert installed[2].name == "adr-0003-secret-scanning-and-credential-leak-defense.md"

    # Verify content was rewritten with new canonical IDs
    c0 = installed[0].read_text(encoding="utf-8")
    assert "# ADR-0001: Zero-Trust Autonomous Worker Process Sandboxing" in c0

    reg_content = registry_file.read_text(encoding="utf-8")
    assert "| ADR-0001 | Zero-Trust Autonomous Worker Process Sandboxing |" in reg_content
    assert "| ADR-0002 | Immutable Supply-Chain Lockfile Enforcement |" in reg_content
    assert "| ADR-0003 | Real-Time Secret Scanning and Credential Leak Defense |" in reg_content

    # Second call is idempotent
    second_install = install_security_adrs(tmp_path)
    assert len(second_install) == 0


def test_install_security_adrs_with_existing_adrs(tmp_path: Path):
    adrs_dir = tmp_path / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    (adrs_dir / "adr-0007-existing-adr.md").write_text("# ADR-0007\n", encoding="utf-8")

    installed = install_security_adrs(tmp_path)
    assert len(installed) == 3
    assert installed[0].name == "adr-0008-zero-trust-worker-process-sandboxing.md"
    assert installed[1].name == "adr-0009-immutable-supply-chain-lockfile-enforcement.md"
    assert installed[2].name == "adr-0010-secret-scanning-and-credential-leak-defense.md"


def test_apply_security_profile_without_existing_toml(tmp_path: Path):
    apply_security_profile(tmp_path)
    toml_path = tmp_path / "specops.toml"
    assert toml_path.is_file()
    assert "[security]" in toml_path.read_text(encoding="utf-8")
    assert (tmp_path / "docs" / "project" / "SECURITY.md").is_file()


def test_apply_security_profile_already_has_security_toml(tmp_path: Path):
    toml_path = tmp_path / "specops.toml"
    toml_path.write_text("[project]\nname = 'Test'\n\n[security]\nsecret_scanning = true\n", encoding="utf-8")
    apply_security_profile(tmp_path)
    content = toml_path.read_text(encoding="utf-8")
    # Must not duplicate [security] block
    assert content.count("[security]") == 1


def test_validate_security_policy_valid(tmp_path: Path):
    sec_md = tmp_path / "docs" / "project" / "SECURITY.md"
    sec_md.parent.mkdir(parents=True, exist_ok=True)
    sec_md.write_text(DEFAULT_SECURITY_MD, encoding="utf-8")

    toml_path = tmp_path / "specops.toml"
    toml_path.write_text('[project]\nname = "SecApp"\n\n' + DEFAULT_SECURITY_TOML, encoding="utf-8")

    ok, msg = validate_security_policy(tmp_path)
    assert ok
    assert "verified" in msg


def test_scaffold_security_policy(tmp_path: Path):
    sec_md = scaffold_security_policy(tmp_path, overwrite=False)
    assert sec_md.is_file()
    assert "Vulnerability Disclosure" in sec_md.read_text(encoding="utf-8")

    # Modify and test overwrite=False preserves modification
    sec_md.write_text("Custom Content That Is Long Enough And Valid\n" * 3, encoding="utf-8")
    scaffold_security_policy(tmp_path, overwrite=False)
    assert "Custom Content" in sec_md.read_text(encoding="utf-8")

    # Overwrite=True restores default
    scaffold_security_policy(tmp_path, overwrite=True)
    assert "Vulnerability Disclosure" in sec_md.read_text(encoding="utf-8")


def test_apply_and_sync_security_profile(tmp_path: Path):
    init_project(tmp_path, name="ApplyTest", profiles=["core", "bdd", "ddd"])

    # Initially no security
    assert not (tmp_path / "docs" / "project" / "SECURITY.md").exists()
    assert "[security]" not in (tmp_path / "specops.toml").read_text(encoding="utf-8")

    apply_security_profile(tmp_path)

    assert (tmp_path / "docs" / "project" / "SECURITY.md").is_file()
    assert "[security]" in (tmp_path / "specops.toml").read_text(encoding="utf-8")
    assert "Security & Supply-Chain Hard Invariants" in (tmp_path / "AGENTS.md").read_text(encoding="utf-8")

    # Delete SECURITY.md and test sync_security_profile
    (tmp_path / "docs" / "project" / "SECURITY.md").unlink()
    assert not (tmp_path / "docs" / "project" / "SECURITY.md").exists()

    sync_security_profile(tmp_path)
    assert (tmp_path / "docs" / "project" / "SECURITY.md").is_file()


def test_cli_profile_apply_and_sync(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    init_project(tmp_path, name="CliProfileTest", profiles=["core"])

    from spec_ops.cli.main import main

    monkeypatch.setattr(sys, "argv", ["spec-ops", "profile", "apply", "security"])
    ret = main()
    assert ret == 0
    captured = capsys.readouterr()
    assert "Applied 'security'" in captured.out

    # Remove SECURITY.md
    (tmp_path / "docs" / "project" / "SECURITY.md").unlink()

    # Health check fails
    monkeypatch.setattr(sys, "argv", ["spec-ops", "health", "--security"])
    ret_fail = main()
    assert ret_fail == 1
    captured_fail = capsys.readouterr()
    assert "Security Policy Invariant Violated" in captured_fail.out

    # Sync restores it
    monkeypatch.setattr(sys, "argv", ["spec-ops", "profile", "sync", "security"])
    ret_sync = main()
    assert ret_sync == 0
    captured_sync = capsys.readouterr()
    assert "Synchronized 'security'" in captured_sync.out

    # Health check now passes
    monkeypatch.setattr(sys, "argv", ["spec-ops", "health", "--security"])
    ret_pass = main()
    assert ret_pass == 0
    captured_pass = capsys.readouterr()
    assert "Security policies and guardrails verified" in captured_pass.out


def test_cli_profile_unknown(tmp_path: Path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    from spec_ops.cli.main import main

    monkeypatch.setattr(sys, "argv", ["spec-ops", "profile", "apply", "nonexistent"])
    ret = main()
    assert ret == 1
    captured = capsys.readouterr()
    assert "Unknown profile" in captured.err

