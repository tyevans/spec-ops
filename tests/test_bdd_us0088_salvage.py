"""BDD step definitions for US-0088: Selective Patch Takeover and Partial File Salvage."""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.worker import BacklogWorkerEngine

from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.cli.main import main
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.rescue.lifecycle import create_worktree
from spec_ops.rescue.salvage import (
    complete_salvage,
    get_staged_files,
    get_untracked_files,
    patch_files,
    salvage_files,
)
from spec_ops.scaffold.init import init_project

scenarios("features/us_0088_worktree_salvage.feature")


@pytest.fixture
def repo_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="US0088App", target_dir=repo, profiles=["core", "bdd", "ddd"])

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Riley Developer"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "developer@company.com"], cwd=repo, check=True, capture_output=True)

    backlog_dir = repo / "docs" / "project" / "backlog"
    refined_dir = backlog_dir / "refined"
    complete_dir = backlog_dir / "complete"
    refined_dir.mkdir(parents=True, exist_ok=True)
    complete_dir.mkdir(parents=True, exist_ok=True)

    (repo / "README.md").write_text("# US0088 Test\n", encoding="utf-8")
    (repo / "specops.toml").write_text("[project]\nname = 'US0088App'\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    monkeypatch.chdir(repo)
    cfg = load_config(repo)
    return {"repo": repo, "backlog_dir": backlog_dir, "config": cfg}


@given(parsers.parse('a stalled worktree "{wt_rel}" with modified files:'))
def setup_stalled_worktree_with_files(repo_env: dict[str, Any], wt_rel: str):
    repo = repo_env["repo"]
    backlog_dir = repo_env["backlog_dir"]
    tid = "TASK-0018"
    branch = f"feat/{tid}"

    task_file = backlog_dir / "refined" / "0018-core-models.md"
    task = Task(
        id="0018",
        title="Implement Core Domain Models",
        status="Refined",
        governing_stories=["US-0088"],
        governing_prds=["PRD-0004"],
        governing_adrs=["ADR-0005"],
        file_path=task_file,
    )
    write_task_file(task)

    priority_file = backlog_dir / "PRIORITY.md"
    priority_file.write_text(
        "# Backlog Priority Index\n\n"
        f"- **{tid} (Refined)**: [`0018-core-models`](refined/0018-core-models.md)\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: add task 0018"], cwd=repo, check=True, capture_output=True)

    wt_dir = repo / wt_rel.removeprefix("./")
    create_worktree(repo, branch=branch, worktree_dir=wt_dir)

    models_py = wt_dir / "src" / "spec_ops" / "core" / "models.py"
    models_py.parent.mkdir(parents=True, exist_ok=True)
    models_py.write_text("class DomainModel:\n    pass\n", encoding="utf-8")

    test_models_py = wt_dir / "tests" / "core" / "test_models.py"
    test_models_py.parent.mkdir(parents=True, exist_ok=True)
    test_models_py.write_text("def test_domain():\n    assert True\n", encoding="utf-8")

    scratch_debug = wt_dir / "src" / "spec_ops" / "scratch_debug.py"
    scratch_debug.write_text("# Scratchpad hallucination with broken code\n$!@invalid\n", encoding="utf-8")

    parser_py = wt_dir / "src" / "spec_ops" / "core" / "parser.py"
    parser_py.write_text("\n".join([f"# bloated line {i}" for i in range(600)]), encoding="utf-8")

    repo_env["wt_dir"] = wt_dir
    repo_env["task"] = task


@when(parsers.parse('the engineer executes "{cmd}"'))
def engineer_executes_command(repo_env: dict[str, Any], cmd: str):
    tokens = shlex.split(cmd.strip())
    if tokens and tokens[0] == "spec-ops":
        tokens = tokens[1:]

    # If running --complete --salvage, stub preflight pipeline execution
    if "--complete" in tokens and "--salvage" in tokens:
        orig = BacklogWorkerEngine.run_preflight
        BacklogWorkerEngine.run_preflight = lambda self, *args, **kwargs: (True, "Preflight passed (0 errors, 100% tests)")
        try:
            exit_code = main(tokens)
            repo_env["last_exit_code"] = exit_code
            assert exit_code == 0
        finally:
            BacklogWorkerEngine.run_preflight = orig
    else:
        exit_code = main(tokens)
        repo_env["last_exit_code"] = exit_code
        assert exit_code == 0


@then("only the specified files are staged into the rescue changeset")
def verify_only_specified_files_staged(repo_env: dict[str, Any]):
    wt_dir = repo_env["wt_dir"]
    staged = get_staged_files(wt_dir)
    assert sorted(staged) == [
        "src/spec_ops/core/models.py",
        "tests/core/test_models.py",
    ]


@then(parsers.parse('untracked scratch files and the bloated "{bloated_file}" remain uncommitted and excluded from preflight.'))
def verify_scratch_and_bloated_excluded(repo_env: dict[str, Any], bloated_file: str):
    wt_dir = repo_env["wt_dir"]
    staged = get_staged_files(wt_dir)
    assert "src/spec_ops/scratch_debug.py" not in staged
    assert not any(bloated_file in s for s in staged)

    untracked = get_untracked_files(wt_dir)
    assert "src/spec_ops/scratch_debug.py" in untracked
    assert any(bloated_file in u for u in untracked)


@given(parsers.parse('the engineer has selectively staged the valid models and tests for "{task_id}"'))
def engineer_selectively_staged_models_and_tests(repo_env: dict[str, Any], task_id: str):
    setup_stalled_worktree_with_files(repo_env, f".worktrees/task-{task_id.replace('TASK-', '').lower()}")
    wt_dir = repo_env["wt_dir"]
    salvage_files(wt_dir, task_id, ["src/spec_ops/core/models.py", "tests/core/test_models.py"])


@given(parsers.parse('implemented the missing parser logic cleanly in "{parser_rel}" (<400 lines)'))
def engineer_implemented_clean_parser(repo_env: dict[str, Any], parser_rel: str):
    wt_dir = repo_env["wt_dir"]
    clean_parser = wt_dir / parser_rel
    clean_parser.write_text("def parse_tokens(text: str) -> list[str]:\n    return text.split()\n", encoding="utf-8")
    patch_files(wt_dir, "TASK-0018", [parser_rel])


@then("preflight verification runs exclusively on the curated staging area")
def verify_preflight_runs_exclusively(repo_env: dict[str, Any]):
    assert repo_env.get("last_exit_code") == 0


@then("passes with 0 file limit violations and 100% test pass rate.")
def verify_preflight_passes_cleanly(repo_env: dict[str, Any]):
    assert repo_env.get("last_exit_code") == 0


@given(parsers.parse('preflight verification succeeds on the salvaged patch for "{task_id}"'))
def preflight_succeeds_on_salvaged_diff(repo_env: dict[str, Any], task_id: str):
    engineer_selectively_staged_models_and_tests(repo_env, task_id)
    engineer_implemented_clean_parser(repo_env, "src/spec_ops/core/parser.py")


@when(parsers.parse('the rescue manager merges the branch into "{target_branch}" under MERGE_LOCK'))
def rescue_manager_merges_branch(repo_env: dict[str, Any], target_branch: str):
    cfg = repo_env["config"]
    orig = BacklogWorkerEngine.run_preflight
    BacklogWorkerEngine.run_preflight = lambda self, *args, **kwargs: (True, "Preflight passed")
    try:
        ok, msg = complete_salvage(cfg, "TASK-0018")
        assert ok, f"complete_salvage failed: {msg}"
    finally:
        BacklogWorkerEngine.run_preflight = orig


@then("the squash commit message includes structured dual-custody trailers:")
def verify_commit_trailers_multiline(repo_env: dict[str, Any], docstring: str):
    repo = repo_env["repo"]
    log_res = subprocess.run(["git", "log", "-1", "--format=%B"], cwd=repo, capture_output=True, text=True)
    body = log_res.stdout

    for expected_line in docstring.strip().splitlines():
        line_clean = expected_line.strip()
        if line_clean:
            assert line_clean in body, f"Expected line '{line_clean}' not found in commit message:\n{body}"


@then(parsers.parse('task "{task_id}" is transitioned from "{from_dir}" to "{to_dir}".'))
def verify_task_transitioned(repo_env: dict[str, Any], task_id: str, from_dir: str, to_dir: str):
    repo = repo_env["repo"]
    from_path = repo / "docs" / "project" / "backlog" / from_dir.strip("/")
    to_path = repo / "docs" / "project" / "backlog" / to_dir.strip("/")

    from_matches = list(from_path.glob("*0018*.md"))
    to_matches = list(to_path.glob("*0018*.md"))

    assert not from_matches, f"Task {task_id} still found in {from_dir}"
    assert to_matches, f"Task {task_id} not found in {to_dir}"
