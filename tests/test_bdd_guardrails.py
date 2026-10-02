"""Executable BDD scenarios for US-0030: Automated Backlog Protection Guardrails."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import BacklogQueue
from spec_ops.worker import BacklogWorkerEngine
from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.worker.guardrails import detect_backlog_modifications

scenarios("features/us_0030_backlog_protection_guardrails.feature")


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    """Initializes a clean git repository scaffolded with SpecOps structure."""
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="WorkerGuardApp", target_dir=repo)

    # Empty out template tasks so test scenarios have total control
    for folder in [
        repo / "docs" / "project" / "backlog" / "refined",
        repo / "docs" / "project" / "backlog" / "proposed",
        repo / "docs" / "project" / "backlog" / "complete",
    ]:
        if folder.exists():
            shutil.rmtree(folder)
        folder.mkdir(parents=True, exist_ok=True)

    # Write clean empty PRIORITY.md
    (repo / "docs" / "project" / "backlog" / "PRIORITY.md").write_text(
        "# Backlog Priority Index\n\n", encoding="utf-8"
    )

    # Dummy passing test
    tests_dir = repo / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    (tests_dir / "test_sample.py").write_text("def test_ok(): pass\n", encoding="utf-8")

    # Git init and commit
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "SpecOps Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@specops.dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    return repo


@pytest.fixture
def bdd_context(test_repo: Path) -> dict[str, Any]:
    cfg = load_config(test_repo)
    cfg.quality.preflight = ["true"]
    return {
        "repo": test_repo,
        "config": cfg,
        "worker_engine": BacklogWorkerEngine(cfg),
        "queue": BacklogQueue(cfg.backlog_dir),
        "worktree_dir": None,
        "cli_result": None,
        "task": None,
        "detected_dirty": [],
    }


# ==============================================================================
# US-0030: Automated Backlog Protection and Accidental Modification Guardrails
# ==============================================================================


@given(parsers.parse('an isolated worktree on branch "{branch}"'))
def isolated_worktree_on_branch(bdd_context: dict[str, Any], test_repo: Path, branch: str):
    engine: BacklogWorkerEngine = bdd_context["worker_engine"]
    wt_dir = test_repo / ".worktrees" / branch.replace("/", "-")
    engine.create_worktree(branch, wt_dir)
    bdd_context["worktree_dir"] = wt_dir


@when(parsers.parse('the agent implements feature code in "{code_dir}"'))
def agent_implements_feature_code(bdd_context: dict[str, Any], code_dir: str):
    wt: Path = bdd_context["worktree_dir"]
    target_dir = wt / code_dir
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "feature.py").write_text("# Feature implementation\ndef run(): return 42\n", encoding="utf-8")


@when(parsers.parse('the agent inadvertently modifies "{file1}" and "{file2}"'))
def agent_modifies_backlog_files(bdd_context: dict[str, Any], file1: str, file2: str):
    wt: Path = bdd_context["worktree_dir"]
    for rel in [file1, file2]:
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"# Accidental edit in {rel}\n", encoding="utf-8")


@when("the worker engine initiates commit preparation")
def worker_initiates_commit_preparation(bdd_context: dict[str, Any]):
    wt: Path = bdd_context["worktree_dir"]
    engine: BacklogWorkerEngine = bdd_context["worker_engine"]
    dirty = detect_backlog_modifications(wt)
    bdd_context["detected_dirty"] = dirty
    ok, msg = engine.prepare_commit(wt, commit_msg="feat: worker implementation")
    bdd_context["commit_result"] = (ok, msg)


@then('the worker detects modifications inside "docs/project/backlog/"')
def worker_detects_backlog_modifications(bdd_context: dict[str, Any]):
    dirty = bdd_context["detected_dirty"]
    assert any("docs/project/backlog" in d for d in dirty)


@then('automatically executes a git checkout HEAD on "docs/project/backlog/" to discard the changes')
def executes_git_checkout_head(bdd_context: dict[str, Any]):
    wt: Path = bdd_context["worktree_dir"]
    st = subprocess.run(["git", "status", "--porcelain", "docs/project/backlog"], cwd=wt, capture_output=True, text=True)
    assert st.stdout.strip() == "", f"Backlog changes were not discarded: {st.stdout}"


@then('stages only legitimate source code and test files in "src/" and "tests/"')
def stages_only_legitimate_files(bdd_context: dict[str, Any]):
    wt: Path = bdd_context["worktree_dir"]
    st = subprocess.run(["git", "diff", "--name-only", "HEAD~1", "HEAD"], cwd=wt, capture_output=True, text=True)
    committed = [line.strip() for line in st.stdout.splitlines() if line.strip()]
    for f in committed:
        assert f.startswith("src/") or f.startswith("tests/"), f"Unexpected committed file: {f}"


@then("creates a commit containing zero modifications to shared backlog indices.")
def commit_contains_zero_backlog_modifications(bdd_context: dict[str, Any]):
    wt: Path = bdd_context["worktree_dir"]
    st = subprocess.run(["git", "diff", "--name-only", "HEAD~1", "HEAD"], cwd=wt, capture_output=True, text=True)
    committed = [line.strip() for line in st.stdout.splitlines() if line.strip()]
    assert not any("docs/project/backlog" in f for f in committed)
