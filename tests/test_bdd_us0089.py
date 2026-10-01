"""BDD step definitions for US-0089: Safe Worktree Discard with Anti-Loop Failure Memory and Task Reset."""

from __future__ import annotations

import re
import shlex
import subprocess
from pathlib import Path
from typing import Any

import pytest
import yaml
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.cli.main import main
from spec_ops.config.loader import load_config
from spec_ops.core.parser import parse_task
from spec_ops.worker.claimer import hydrate_task_prompt

scenarios("features/us_0089_safe_worktree_reset.feature")


@pytest.fixture
def repo_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()

    # Initialize minimal git repository
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "SpecOps Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@specops.test"], cwd=repo, check=True, capture_output=True)

    # Backlog structure
    backlog_dir = repo / "docs" / "project" / "backlog"
    refined_dir = backlog_dir / "refined"
    proposed_dir = backlog_dir / "proposed"
    complete_dir = backlog_dir / "complete"
    refined_dir.mkdir(parents=True)
    proposed_dir.mkdir(parents=True)
    complete_dir.mkdir(parents=True)

    # Initial commit so HEAD exists
    (repo / "README.md").write_text("# Test Repo\n", encoding="utf-8")
    (repo / "specops.toml").write_text("[project]\nname = 'TestRepo'\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    monkeypatch.chdir(repo)
    cfg = load_config(repo)
    return {"repo": repo, "backlog_dir": backlog_dir, "config": cfg}


@given(parsers.parse('a stalled worktree "{wt_rel}" where the agent attempted an invalid monkey-patching approach'))
def setup_stalled_worktree(repo_env: dict[str, Any], wt_rel: str):
    repo = repo_env["repo"]
    backlog_dir = repo_env["backlog_dir"]
    tid = "TASK-0024"
    branch = f"feat/{tid}"

    # Create task file in refined
    task_file = backlog_dir / "refined" / "0024-invalid-mock-task.md"
    task_file.write_text(
        "---\n"
        "id: '0024'\n"
        "title: Monkey Patching Task\n"
        "status: Refined\n"
        "governing_adrs:\n"
        "  - ADR-0003\n"
        "---\n\n"
        "# Task: TASK-0024\n"
        "Some details here.\n",
        encoding="utf-8",
    )

    # Add to PRIORITY.md
    priority_file = backlog_dir / "PRIORITY.md"
    priority_file.write_text(
        "# Backlog Priority Index\n\n"
        f"- **{tid} (Refined)**: [`0024-invalid-mock-task`](refined/0024-invalid-mock-task.md)\n",
        encoding="utf-8",
    )

    # Create git worktree
    wt_dir = repo / wt_rel.removeprefix("./")
    subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(wt_dir), "main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    (wt_dir / "monkeypatch.py").write_text("# Bad monkeypatch\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=wt_dir, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "wip: monkey patch"], cwd=wt_dir, check=True, capture_output=True)

    repo_env["wt_dir"] = wt_dir
    repo_env["branch"] = branch
    repo_env["task_file"] = task_file


@when("the engineer executes:")
def engineer_executes_multiline_cmd(repo_env: dict[str, Any], docstring: str):
    args = shlex.split(docstring.strip())
    if args and args[0] == "spec-ops":
        args = args[1:]
    exit_code = main(args)
    assert exit_code == 0


@then(parsers.parse('the git worktree "{wt_rel}" and branch "{branch_name}" are deleted'))
def worktree_and_branch_deleted(repo_env: dict[str, Any], wt_rel: str, branch_name: str):
    repo = repo_env["repo"]
    wt_dir = repo / wt_rel.removeprefix("./")
    assert not wt_dir.exists(), f"Worktree {wt_dir} still exists"

    res = subprocess.run(["git", "branch", "--list", branch_name], cwd=repo, capture_output=True, text=True)
    assert branch_name not in res.stdout, f"Branch {branch_name} still exists"


@then(parsers.parse('the task specification file "{file_glob}" is updated with frontmatter metadata:'))
def task_file_updated_with_frontmatter(repo_env: dict[str, Any], file_glob: str, docstring: str):
    repo = repo_env["repo"]
    matches = list(repo.glob(file_glob))
    assert matches, f"No files matched glob {file_glob}"
    task_file = matches[0]

    content = task_file.read_text(encoding="utf-8")
    match = re.search(r"^---\s*\n(.*?)\n---", content, re.DOTALL)
    assert match, "YAML frontmatter not found in task file"
    meta = yaml.safe_load(match.group(1))

    assert "failure_history" in meta
    history = meta["failure_history"]
    assert len(history) >= 1

    entry = history[-1]
    assert "reason" in entry
    assert "Agent attempted internal mock backdoors" in entry["reason"]
    assert "ADR-0003" in str(entry.get("failed_invariants", []))


@then(parsers.parse('task "{task_id}" remains in "{dir_rel}" for re-assignment.'))
def task_remains_in_folder(repo_env: dict[str, Any], task_id: str, dir_rel: str):
    repo = repo_env["repo"]
    target_dir = repo / dir_rel
    matches = [p for p in target_dir.glob("*.md") if "0024" in p.name]
    assert matches, f"Task {task_id} not found in {target_dir}"


@given(parsers.parse('an engineer determines that "{task_id}" stalled because acceptance criteria were contradictory'))
def engineer_determines_stalled(repo_env: dict[str, Any], task_id: str):
    repo = repo_env["repo"]
    backlog_dir = repo_env["backlog_dir"]
    branch = f"feat/{task_id}"

    task_file = backlog_dir / "refined" / "0030-contradictory-criteria.md"
    task_file.write_text(
        "---\n"
        "id: '0030'\n"
        "title: Contradictory Task\n"
        "status: Refined\n"
        "---\n\n"
        "# Task: TASK-0030\n"
        "Criteria contradictory.\n",
        encoding="utf-8",
    )

    priority_file = backlog_dir / "PRIORITY.md"
    priority_file.write_text(
        "# Backlog Priority Index\n\n"
        f"- **{task_id} (Refined)**: [`0030-contradictory-criteria`](refined/0030-contradictory-criteria.md)\n",
        encoding="utf-8",
    )

    wt_dir = repo / ".worktrees" / "task-0030"
    subprocess.run(
        ["git", "worktree", "add", "-b", branch, str(wt_dir), "main"],
        cwd=repo,
        check=True,
        capture_output=True,
    )
    repo_env["wt_dir_30"] = wt_dir
    repo_env["branch_30"] = branch


@when(parsers.parse('the engineer executes "{command_str}"'))
def engineer_executes_single_line_cmd(repo_env: dict[str, Any], command_str: str):
    args = shlex.split(command_str)
    if args and args[0] == "spec-ops":
        args = args[1:]
    exit_code = main(args)
    assert exit_code == 0


@then('the worktree and branch are cleaned up')
def worktree_and_branch_cleaned_up(repo_env: dict[str, Any]):
    wt_dir = repo_env.get("wt_dir_30")
    if wt_dir:
        assert not wt_dir.exists()


@then(parsers.parse('the task file is moved from "{src_dir}" to "{dst_dir}"'))
def task_file_moved(repo_env: dict[str, Any], src_dir: str, dst_dir: str):
    repo = repo_env["repo"]
    src = repo / src_dir
    dst = repo / dst_dir

    src_files = [p for p in src.glob("*.md") if "0030" in p.name]
    assert not src_files, f"File still present in {src}"

    dst_files = [p for p in dst.glob("*.md") if "0030" in p.name]
    assert dst_files, f"File not found in {dst}"


@then(parsers.parse('"{priority_rel}" is synchronized without task "{task_id}" blocking the refined queue.'))
def priority_synchronized(repo_env: dict[str, Any], priority_rel: str, task_id: str):
    repo = repo_env["repo"]
    priority_file = repo / priority_rel
    content = priority_file.read_text(encoding="utf-8")

    assert f"**{task_id} (Proposed)**" in content
    assert "proposed/0030-" in content
    assert f"**{task_id} (Refined)**" not in content


@given(parsers.parse('task "{task_id}" has recorded failure history citing "{reason_pattern}"'))
def task_has_recorded_failure_history(repo_env: dict[str, Any], task_id: str, reason_pattern: str):
    backlog_dir = repo_env["backlog_dir"]
    task_file = backlog_dir / "refined" / "0024-invalid-mock-task.md"
    task_file.write_text(
        "---\n"
        "id: '0024'\n"
        "title: Monkey Patching Task\n"
        "status: Refined\n"
        "governing_adrs:\n"
        "  - ADR-0003\n"
        "failure_history:\n"
        "  - attempt_date: '2026-09-29'\n"
        '    reason: "Agent attempted internal mock backdoors violating ADR-0003 instead of public CLI testing"\n'
        "    failed_invariants:\n"
        "      - ADR-0003\n"
        "---\n\n"
        "# Task: TASK-0024\n"
        "Details...\n",
        encoding="utf-8",
    )
    repo_env["task_24_file"] = task_file


@when(parsers.parse('an autonomous worker claims "{task_id}" for a new attempt'))
def autonomous_worker_claims_task(repo_env: dict[str, Any], task_id: str):
    repo = repo_env["repo"]
    cfg = repo_env["config"]
    task_file = repo_env["task_24_file"]

    task = parse_task(task_file)
    prompt_str = hydrate_task_prompt(task, cfg)
    prompt_file = repo / ".task-prompt.md"
    prompt_file.write_text(prompt_str, encoding="utf-8")
    repo_env["generated_prompt"] = prompt_str


@then(parsers.parse('the generated ".task-prompt.md" includes a dedicated section:'))
def prompt_includes_dedicated_section(repo_env: dict[str, Any], docstring: str):
    prompt_str = repo_env["generated_prompt"]
    for line in docstring.strip().splitlines():
        clean_line = line.strip()
        if clean_line:
            assert clean_line in prompt_str, f"Line '{clean_line}' not found in prompt:\n{prompt_str}"
