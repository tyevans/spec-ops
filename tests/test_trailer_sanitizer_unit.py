"""Unit tests for spec_ops.security.trailer_sanitizer to maximize mutant kill rate."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import pytest

from spec_ops.cli.trailer_handler import handle_check_trailers_command
from spec_ops.config.models import SpecOpsConfig
from spec_ops.security.trailer_sanitizer import (
    CommitValidationResult,
    TrailerSanitizer,
    parse_rfc822_trailers,
)


def test_parse_rfc822_trailers_basic_and_folded():
    msg = """feat: add cool feature

Some body text here.

SpecOps-Task: TASK-0042
SpecOps-Story: US-0010,
   US-0011
SpecOps-PRD: PRD-0001
Custom-Key: value:with:colons
Invalid trailer line without colon
Another-Key: Final Value
"""
    trailers = parse_rfc822_trailers(msg)
    assert trailers["SpecOps-Task"] == "TASK-0042"
    assert trailers["SpecOps-Story"] == "US-0010, US-0011"
    assert trailers["SpecOps-PRD"] == "PRD-0001"
    assert trailers["Custom-Key"] == "value:with:colons"
    assert trailers["Another-Key"] == "Final Value"
    assert "Invalid" not in trailers


def test_validate_commit_message_empty():
    sanitizer = TrailerSanitizer()
    res = sanitizer.validate_commit_message("")
    assert not res.is_valid
    assert not res.conventional_valid
    assert "empty" in res.errors[0]


def test_validate_commit_message_non_conventional():
    sanitizer = TrailerSanitizer()
    res = sanitizer.validate_commit_message("WIP fixing stuff\n\nSpecOps-Task: TASK-0001")
    assert not res.is_valid
    assert not res.conventional_valid
    assert any("does not conform" in err for err in res.errors)


def test_validate_commit_message_missing_task_trailer():
    sanitizer = TrailerSanitizer(strict=True)
    res = sanitizer.validate_commit_message("feat(core): new capability\n\nSpecOps-Story: US-0001")
    assert not res.is_valid
    assert res.conventional_valid
    assert "SpecOps-Task" in res.missing_trailers


def test_validate_commit_message_with_unresolved_references(tmp_path: Path):
    # Create docs/project tree without the referenced entity
    project_dir = tmp_path / "docs" / "project"
    (project_dir / "backlog").mkdir(parents=True, exist_ok=True)
    (project_dir / "backlog" / "0001-real-task.md").write_text("# Task\n", encoding="utf-8")

    # Non-strict mode produces warning
    sanitizer_warn = TrailerSanitizer(root_dir=tmp_path, strict=False)
    msg = "feat(core): good commit\n\nSpecOps-Task: TASK-0001\nSpecOps-Story: US-9999"
    res_warn = sanitizer_warn.validate_commit_message(msg)
    assert res_warn.is_valid
    assert len(res_warn.warnings) == 1
    assert "Story US-9999" in res_warn.warnings[0]

    # Strict mode produces error
    sanitizer_strict = TrailerSanitizer(root_dir=tmp_path, strict=True)
    res_strict = sanitizer_strict.validate_commit_message(msg)
    assert not res_strict.is_valid
    assert any("Story US-9999" in err for err in res_strict.errors)


def test_cli_trailer_handler(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    # Initialize real git repo
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=tmp_path, check=True, capture_output=True)

    (tmp_path / "file.txt").write_text("content", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=tmp_path, check=True, capture_output=True)
    msg = "feat: add feature\n\nSpecOps-Task: TASK-0001"
    subprocess.run(["git", "commit", "-m", msg], cwd=tmp_path, check=True, capture_output=True)

    config = SpecOpsConfig(root_dir=tmp_path)

    # 1. Successful text validation
    args_text = argparse.Namespace(rev_range="HEAD~1..HEAD", strict=True, json=False)
    assert handle_check_trailers_command(args_text, config) == 0
    out = capsys.readouterr().out
    assert "All commits comply" in out

    # 2. Successful JSON validation
    args_json = argparse.Namespace(rev_range="HEAD~1..HEAD", strict=True, json=True)
    assert handle_check_trailers_command(args_json, config) == 0
    data = json.loads(capsys.readouterr().out)
    assert len(data) == 1
    assert data[0]["is_valid"] is True
    assert data[0]["trailers"]["SpecOps-Task"] == "TASK-0001"
