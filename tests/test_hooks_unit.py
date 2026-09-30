"""Unit tests for PreCommitHookEvaluator and local git hook utilities."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.worker.hooks import (
    HookEvaluationResult,
    PreCommitHookEvaluator,
    install_pre_commit_hook,
    run_spec_ops_health_hook,
)


@pytest.fixture
def clean_hook_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "hook_repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="HookUnitTestApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "HookTester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "hook@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo, check=True, capture_output=True)

    return repo


def test_evaluator_clean_repo(clean_hook_repo: Path):
    evaluator = PreCommitHookEvaluator(root_dir=clean_hook_repo)
    res = evaluator.evaluate()
    assert res.success is True
    assert res.exit_code == 0
    assert res.violations_count == 0
    assert "Zero source files exceed length limit" in res.output
    assert "PRIORITY.md is synchronized with disk state" in res.output


def test_evaluator_violation(clean_hook_repo: Path):
    src = clean_hook_repo / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "huge.py").write_text("\n".join([f"# line {i}" for i in range(510)]) + "\n", encoding="utf-8")

    evaluator = PreCommitHookEvaluator(root_dir=clean_hook_repo)
    res = evaluator.evaluate()
    assert res.success is False
    assert res.exit_code == 1
    assert res.violations_count == 1
    assert "File Length Violation" in res.output
    assert "huge.py" in res.output


def test_evaluator_warning_threshold(clean_hook_repo: Path):
    src = clean_hook_repo / "src"
    src.mkdir(parents=True, exist_ok=True)
    (src / "medium.py").write_text("\n".join([f"# line {i}" for i in range(415)]) + "\n", encoding="utf-8")

    evaluator = PreCommitHookEvaluator(root_dir=clean_hook_repo)
    res = evaluator.evaluate()
    assert res.success is True
    assert res.exit_code == 0
    assert res.violations_count == 0
    assert res.warnings_count == 1
    assert "Proactive Refactoring Warning" in res.output
    assert "medium.py" in res.output


def test_install_pre_commit_hook(clean_hook_repo: Path):
    hook_file = install_pre_commit_hook(clean_hook_repo)
    assert hook_file.is_file()
    assert hook_file.stat().st_mode & 0o111  # executable
    content = hook_file.read_text(encoding="utf-8")
    assert "spec-ops health" in content


def test_run_spec_ops_health_hook_helper(clean_hook_repo: Path):
    res = run_spec_ops_health_hook(clean_hook_repo)
    assert isinstance(res, HookEvaluationResult)
    assert res.success is True
