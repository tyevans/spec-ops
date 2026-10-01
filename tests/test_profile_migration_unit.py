"""Comprehensive unit tests for ProfileMigrator and ProfileMigrationReport."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

import pytest
import yaml

from spec_ops.core.profile_migration import ProfileMigrationReport, ProfileMigrator


def test_profile_migration_report_methods() -> None:
    report = ProfileMigrationReport(
        from_version="1.0.0",
        to_version="2.0.0",
        is_up_to_date=False,
        applied_steps=["Step 1", "Step 2"],
        changes=["change 1"],
        warnings=["warning 1"],
    )

    d = report.to_dict()
    assert d["from_version"] == "1.0.0"
    assert d["to_version"] == "2.0.0"
    assert d["is_up_to_date"] is False
    assert len(d["applied_steps"]) == 2
    assert len(d["changes"]) == 1
    assert len(d["warnings"]) == 1

    summary = report.summary()
    assert "Migrated profile" in summary
    assert "1.0.0" in summary
    assert "2.0.0" in summary

    up_to_date_report = ProfileMigrationReport(
        from_version="2.0.0",
        to_version="2.0.0",
        is_up_to_date=True,
    )
    assert "up to date" in up_to_date_report.summary()


def test_profile_migrator_detect_version() -> None:
    migrator = ProfileMigrator()

    assert migrator.detect_version({}) == "1.0.0"
    assert migrator.detect_version({"schema_version": "2.0.0"}) == "2.0.0"
    assert migrator.detect_version({"schema_version": "v2.0"}) == "2.0.0"
    assert migrator.detect_version({"schema_version": "2"}) == "2.0.0"
    assert migrator.detect_version({"version": "1.0.0"}) == "1.0.0"
    assert migrator.detect_version({"version": "v1.0"}) == "1.0.0"
    assert migrator.detect_version({"version": 1}) == "1.0.0"
    assert migrator.detect_version({"version": "2.0.0"}) == "2.0.0"
    assert migrator.detect_version({"profile": "core"}) == "1.0.0"


def test_profile_migrator_validate_schema_v2() -> None:
    migrator = ProfileMigrator()

    # Missing schema_version
    errs = migrator.validate_schema({"profiles": ["core"]}, version="2.0.0")
    assert any("schema_version" in e for e in errs)

    # Incompatible version
    errs = migrator.validate_schema({"schema_version": "1.0.0", "profiles": ["core"]}, version="2.0.0")
    assert any("Incompatible schema version" in e for e in errs)

    # Missing profile identifier
    errs = migrator.validate_schema({"schema_version": "2.0.0"}, version="2.0.0")
    assert any("must specify" in e for e in errs)

    # Non-list profiles
    errs = migrator.validate_schema({"schema_version": "2.0.0", "profiles": "not-a-list"}, version="2.0.0")
    assert any("'profiles' must be a list" in e for e in errs)

    # Non-string entries in profiles
    errs = migrator.validate_schema({"schema_version": "2.0.0", "profiles": [123]}, version="2.0.0")
    assert any("must be strings" in e for e in errs)

    # Invalid overrides type
    errs = migrator.validate_schema({"schema_version": "2.0.0", "profiles": ["core"], "overrides": "invalid"}, version="2.0.0")
    assert any("'overrides' must be a dictionary" in e for e in errs)

    # Valid schema v2
    valid_data = {
        "schema_version": "2.0.0",
        "profiles": ["core", "security"],
        "invariants": ["rule-1"],
        "overrides": {"file_length_limit": 450},
        "custom_rules": ["my-custom-rule"],
    }
    assert migrator.validate_schema(valid_data, version="2.0.0") == []


def test_migrate_non_existent_file(tmp_path: Path) -> None:
    migrator = ProfileMigrator()
    missing_file = tmp_path / "does_not_exist.yaml"
    success, report = migrator.migrate(missing_file)
    assert success is False
    assert report.is_up_to_date is False
    assert any("not found" in w for w in report.warnings)


def test_migrate_invalid_yaml(tmp_path: Path) -> None:
    migrator = ProfileMigrator()
    bad_file = tmp_path / "bad.yaml"
    bad_file.write_text("invalid: yaml: [unclosed", encoding="utf-8")
    success, report = migrator.migrate(bad_file)
    assert success is False
    assert any("parsing error" in w for w in report.warnings)


def test_migrate_dry_run_does_not_modify_disk(tmp_path: Path) -> None:
    migrator = ProfileMigrator()
    p_file = tmp_path / "profile.yaml"
    original_text = "profile: core\nversion: 1.0.0\n"
    p_file.write_text(original_text, encoding="utf-8")

    success, report = migrator.migrate(p_file, target_version="2.0.0", dry_run=True)
    assert success is True
    assert report.from_version == "1.0.0"
    assert report.to_version == "2.0.0"
    assert len(report.changes) > 0

    # Ensure disk content is identical
    assert p_file.read_text(encoding="utf-8") == original_text


def test_migrate_already_up_to_date_file(tmp_path: Path) -> None:
    migrator = ProfileMigrator()
    p_file = tmp_path / "profile.yaml"
    content = "schema_version: '2.0.0'\nprofiles:\n  - core\n"
    p_file.write_text(content, encoding="utf-8")

    success, report = migrator.migrate(p_file, target_version="2.0.0")
    assert success is True
    assert report.is_up_to_date is True
    assert report.changes == []
    assert report.applied_steps == []


def test_migrate_consolidates_limits_and_preserves_custom_keys(tmp_path: Path) -> None:
    migrator = ProfileMigrator()
    p_file = tmp_path / "profile.yaml"
    content = """---
profile: core
version: 1.0.0
file_length_limit: 420
require_mutation_testing: true
custom_flag: enabled
custom_list:
  - a
  - b
---
# Markdown body comments
"""
    p_file.write_text(content, encoding="utf-8")

    success, report = migrator.migrate(p_file, target_version="2.0.0")
    assert success is True
    assert report.to_version == "2.0.0"

    updated = p_file.read_text(encoding="utf-8")
    assert "Markdown body comments" in updated

    raw_yaml = updated.split("---")[1]
    data = yaml.safe_load(raw_yaml)

    assert data["schema_version"] == "2.0.0"
    assert data["profiles"] == ["core"]
    assert data["overrides"]["file_length_limit"] == 420
    assert data["overrides"]["require_mutation_testing"] is True
    assert data["custom_flag"] == "enabled"
    assert data["custom_list"] == ["a", "b"]


def test_cli_profile_migrate_custom_path_and_json(tmp_path: Path) -> None:
    custom_profile = tmp_path / "custom_profile.yaml"
    custom_profile.write_text("profile: security\nversion: 1.0.0\n", encoding="utf-8")

    # Run CLI command with --path and --json
    cmd = [
        sys.executable,
        "-m",
        "spec_ops.cli.main",
        "profile",
        "migrate",
        "--path",
        str(custom_profile),
        "--json",
    ]
    res = subprocess.run(cmd, cwd=tmp_path, capture_output=True, text=True)
    assert res.returncode == 0, f"Error: {res.stderr}\n{res.stdout}"

    data = json.loads(res.stdout)
    assert data["from_version"] == "1.0.0"
    assert data["to_version"] == "2.0.0"
    assert "applied_steps" in data

    # Re-run in --check mode with --json
    check_cmd = [
        sys.executable,
        "-m",
        "spec_ops.cli.main",
        "profile",
        "migrate",
        "--path",
        str(custom_profile),
        "--check",
        "--json",
    ]
    res_check = subprocess.run(check_cmd, cwd=tmp_path, capture_output=True, text=True)
    assert res_check.returncode == 0
    check_data = json.loads(res_check.stdout)
    assert check_data["is_up_to_date"] is True


def test_cli_profile_migrate_check_fails_when_outdated(tmp_path: Path) -> None:
    legacy_profile = tmp_path / "legacy.yaml"
    legacy_profile.write_text("profile: core\nversion: 1.0.0\n", encoding="utf-8")

    check_cmd = [
        sys.executable,
        "-m",
        "spec_ops.cli.main",
        "profile",
        "migrate",
        "--path",
        str(legacy_profile),
        "--check",
    ]
    res = subprocess.run(check_cmd, cwd=tmp_path, capture_output=True, text=True)
    assert res.returncode == 1
    assert "requires migration" in res.stderr
