"""Unit tests for src/spec_ops/cli/schema_handler.py."""

from __future__ import annotations

import argparse
from pathlib import Path

from spec_ops.cli.schema_handler import handle_schema_command
from spec_ops.config.models import SpecOpsConfig


def test_schema_handler_no_action(capsys):
    cfg = SpecOpsConfig(root_dir=Path("."))
    args = argparse.Namespace(schema_action=None)
    rc = handle_schema_command(args, cfg)
    assert rc == 0
    assert "Usage: spec-ops schema" in capsys.readouterr().out


def test_schema_handler_check_valid(tmp_path: Path, capsys):
    docs = tmp_path / "docs" / "project" / "backlog" / "refined"
    docs.mkdir(parents=True)
    task = docs / "task-0001.md"
    task.write_text(
        "---\n"
        "id: '0001'\n"
        "title: Title\n"
        "status: Refined\n"
        "target_bc: core\n"
        "governing_adrs: ['ADR-0001']\n"
        "---\n"
    )
    cfg = SpecOpsConfig(root_dir=tmp_path)
    args = argparse.Namespace(schema_action="check", opt_path=None, path=None)
    rc = handle_schema_command(args, cfg)
    assert rc == 0
    assert "Schema Check Passed: All specification documents conform to schema v2.0" in capsys.readouterr().out


def test_schema_handler_check_invalid(tmp_path: Path, capsys):
    docs = tmp_path / "docs" / "project" / "backlog" / "refined"
    docs.mkdir(parents=True)
    task = docs / "task-0001.md"
    task.write_text(
        "---\n"
        "id: '0001'\n"
        "status: Refined\n"
        "---\n"
    )
    cfg = SpecOpsConfig(root_dir=tmp_path)
    args = argparse.Namespace(schema_action="validate", opt_path=None, path=None)
    rc = handle_schema_command(args, cfg)
    assert rc == 1
    assert "Schema Validation Failed" in capsys.readouterr().out


def test_schema_handler_migrate(tmp_path: Path, capsys):
    docs = tmp_path / "docs" / "project" / "backlog" / "refined"
    docs.mkdir(parents=True)
    task = docs / "task-0001.md"
    task.write_text(
        "---\n"
        "id: '0001'\n"
        "title: Title\n"
        "status: Refined\n"
        "target_bc: core\n"
        "governing_adr: 1\n"
        "---\n\n# Body\n"
    )
    cfg = SpecOpsConfig(root_dir=tmp_path)

    # Dry-run
    args = argparse.Namespace(schema_action="migrate", opt_path=None, path=None, dry_run=True, in_place=False)
    rc = handle_schema_command(args, cfg)
    assert rc == 0
    out = capsys.readouterr().out
    assert "-governing_adr: 1" in out
    assert "+governing_adrs:" in out
    assert "governing_adr: 1" in task.read_text(encoding="utf-8")

    # In-place
    args = argparse.Namespace(schema_action="migrate", opt_path=None, path=None, dry_run=False, in_place=True)
    rc = handle_schema_command(args, cfg)
    assert rc == 0
    out = capsys.readouterr().out
    assert "Successfully migrated 1 specification document(s) in-place" in out
    assert "governing_adrs:" in task.read_text(encoding="utf-8")

    # Second pass - no migrations needed
    rc = handle_schema_command(args, cfg)
    assert rc == 0
    assert "No migrations required" in capsys.readouterr().out


def test_schema_handler_unknown_action(capsys):
    cfg = SpecOpsConfig(root_dir=Path("."))
    args = argparse.Namespace(schema_action="unknown", opt_path=None, path=None)
    rc = handle_schema_command(args, cfg)
    assert rc == 0
