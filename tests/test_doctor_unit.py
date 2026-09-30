"""Unit tests for developer environment doctor diagnostic and repair routines."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from spec_ops.config.models import ArchitectureSettings, ProjectSettings, SpecOpsConfig
from spec_ops.rescue.doctor import (
    DeveloperEnvironmentDoctor,
    DoctorCheckResult,
    DoctorReport,
    handle_doctor_command,
)


def test_doctor_report_properties():
    r_pass1 = DoctorCheckResult("comp1", "chk1", "PASS")
    r_pass2 = DoctorCheckResult("comp2", "chk2", "PASS")
    r_fail = DoctorCheckResult("comp3", "chk3", "FAIL", message="bad", fixable=True)

    rep_healthy = DoctorReport(results=[r_pass1, r_pass2])
    assert rep_healthy.is_healthy is True
    assert rep_healthy.issues_count == 0

    rep_unhealthy = DoctorReport(results=[r_pass1, r_fail])
    assert rep_unhealthy.is_healthy is False
    assert rep_unhealthy.issues_count == 1


def test_check_uv_missing(tmp_path: Path):
    doc = DeveloperEnvironmentDoctor(root_dir=tmp_path)
    with patch("shutil.which", return_value=None):
        res = doc.check_uv()
        assert res.status == "FAIL"
        assert "UV is not installed" in res.message


def test_check_uv_missing_pyproject(tmp_path: Path):
    doc = DeveloperEnvironmentDoctor(root_dir=tmp_path)
    with patch("shutil.which", return_value="/usr/bin/uv"):
        res = doc.check_uv()
        assert res.status == "FAIL"
        assert "pyproject.toml not found" in res.message


def test_check_uv_pass_and_fail(tmp_path: Path):
    (tmp_path / "pyproject.toml").write_text("[project]\nname='app'\n", encoding="utf-8")
    doc = DeveloperEnvironmentDoctor(root_dir=tmp_path)

    # Pass case
    mock_ok = MagicMock(returncode=0)
    with patch("shutil.which", return_value="/usr/bin/uv"), patch("subprocess.run", return_value=mock_ok):
        res = doc.check_uv()
        assert res.status == "PASS"

    # Fail case
    mock_fail = MagicMock(returncode=1)
    with patch("shutil.which", return_value="/usr/bin/uv"), patch("subprocess.run", return_value=mock_fail):
        res = doc.check_uv()
        assert res.status == "FAIL"
        assert res.fixable is True

    # Exception case
    with patch("shutil.which", return_value="/usr/bin/uv"), patch("subprocess.run", side_effect=OSError("disk error")):
        res = doc.check_uv()
        assert res.status == "FAIL"
        assert "Failed to execute" in res.message


def test_check_git_worktrees(tmp_path: Path):
    doc = DeveloperEnvironmentDoctor(root_dir=tmp_path)

    # Missing .gitignore
    res = doc.check_git_worktrees()
    assert res.status == "FAIL"
    assert res.fixable is True

    # Existing but missing .worktrees
    gi = tmp_path / ".gitignore"
    gi.write_text("*.pyc\n__pycache__/\n", encoding="utf-8")
    res2 = doc.check_git_worktrees()
    assert res2.status == "FAIL"

    # Configured with .worktrees/
    gi.write_text("*.pyc\n.worktrees/\n", encoding="utf-8")
    res3 = doc.check_git_worktrees()
    assert res3.status == "PASS"

    # Configured with .worktrees
    gi.write_text("*.pyc\n.worktrees\n", encoding="utf-8")
    res4 = doc.check_git_worktrees()
    assert res4.status == "PASS"


def test_check_pre_commit_hooks(tmp_path: Path):
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    doc = DeveloperEnvironmentDoctor(root_dir=tmp_path)

    # Missing hook file
    res = doc.check_pre_commit_hooks()
    assert res.status == "FAIL"

    # Existing but not executable
    hook_file = hooks_dir / "pre-commit"
    hook_file.write_text("echo 'hello'\n", encoding="utf-8")
    hook_file.chmod(0o644)
    res2 = doc.check_pre_commit_hooks()
    assert res2.status == "FAIL"
    assert "not executable" in res2.message

    # Executable but missing spec-ops health
    hook_file.chmod(0o755)
    res3 = doc.check_pre_commit_hooks()
    assert res3.status == "FAIL"
    assert "does not invoke spec-ops health" in res3.message

    # Executable with spec-ops health
    hook_file.write_text("#!/bin/sh\nuv run spec-ops health\n", encoding="utf-8")
    hook_file.chmod(0o755)
    res4 = doc.check_pre_commit_hooks()
    assert res4.status == "PASS"


def test_check_line_limits(tmp_path: Path):
    cfg = SpecOpsConfig(
        root_dir=tmp_path,
        project=ProjectSettings(name="LineLimitTest"),
        architecture=ArchitectureSettings(file_length_limit=500),
    )
    doc = DeveloperEnvironmentDoctor(root_dir=tmp_path, config=cfg)

    # Zero violations
    res = doc.check_line_limits()
    assert res.status == "PASS"

    # Oversized violation
    src_file = tmp_path / "src" / "bloated.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("\n".join(f"# line {i}" for i in range(550)) + "\n", encoding="utf-8")

    res2 = doc.check_line_limits()
    assert res2.status == "FAIL"
    assert "violate length limits" in res2.message


def test_doctor_repair_fix(tmp_path: Path):
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='app'\n", encoding="utf-8")
    doc = DeveloperEnvironmentDoctor(root_dir=tmp_path)

    repairs = doc.fix()
    assert any("gitignore" in r.lower() for r in repairs)
    assert any("pre-commit hook" in r.lower() for r in repairs)

    # Verify repairs on disk
    gi = tmp_path / ".gitignore"
    assert gi.is_file()
    assert ".worktrees/" in gi.read_text(encoding="utf-8")
    assert (tmp_path / ".worktrees").is_dir()

    hook_file = hooks_dir / "pre-commit"
    assert hook_file.is_file()
    assert os.access(hook_file, os.X_OK)
    assert "spec-ops health" in hook_file.read_text(encoding="utf-8")


def test_handle_doctor_command_json_and_cli(tmp_path: Path, capsys: pytest.CaptureFixture[str]):
    hooks_dir = tmp_path / ".git" / "hooks"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    (tmp_path / "pyproject.toml").write_text("[project]\nname='app'\n", encoding="utf-8")
    cfg = SpecOpsConfig(root_dir=tmp_path)

    # 1. Unhealthy run
    args = argparse.Namespace(fix=False, json=False)
    ret = handle_doctor_command(args, cfg)
    assert ret == 1
    out = capsys.readouterr().out
    assert "issue" in out
    assert "spec-ops doctor --fix" in out

    # 2. JSON output mode
    args_json = argparse.Namespace(fix=False, json=True)
    ret_json = handle_doctor_command(args_json, cfg)
    assert ret_json == 1
    out_json = capsys.readouterr().out
    data = json.loads(out_json)
    assert data["is_healthy"] is False
    assert len(data["checks"]) == 4

    # 3. Healthy run after fix
    with patch("subprocess.run", return_value=MagicMock(returncode=0)):
        args_fix = argparse.Namespace(fix=True, json=False)
        ret_fix = handle_doctor_command(args_fix, cfg)
        assert ret_fix == 0
        out_fix = capsys.readouterr().out
        assert "Development environment is healthy and ready for active engineering." in out_fix
