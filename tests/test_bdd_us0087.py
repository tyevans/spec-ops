"""BDD step definitions for US-0087: Interactive Preserved Worktree Triage and Failure Diagnostic Breakdown."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import write_task_file
from spec_ops.cli.parser import build_parser
from spec_ops.cli.rescue_handler import handle_rescue_command
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.rescue.lifecycle import create_worktree
from spec_ops.scaffold.init import init_project

scenarios("features/us_0087_interactive_worktree_triage.feature")


@pytest.fixture
def triage_ctx(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()

    init_project(name="TriageApp", target_dir=repo, profiles=["core", "bdd", "ddd"])

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Riley Developer"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "riley@specops.test"], cwd=repo, check=True, capture_output=True)

    # Initial file for parser with 472 lines
    parser_file = repo / "src" / "spec_ops" / "core" / "parser.py"
    parser_file.parent.mkdir(parents=True, exist_ok=True)
    lines_472 = ["# parser file header\n"] + [f"def parse_item_{i}():\n    return {i}\n" for i in range(235)] + ["\n"]
    parser_file.write_text("".join(lines_472), encoding="utf-8")

    # Initial test file
    test_file = repo / "tests" / "test_parser.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def test_parse_syntax():\n    assert True\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    cfg = load_config(repo)
    return {"repo": repo, "config": cfg}


@given(parsers.parse('an autonomous worker session for "{task_id}" has exhausted its {attempts:d} self-healing attempts'))
def worker_exhausted_attempts(triage_ctx: dict[str, Any], task_id: str, attempts: int):
    cfg = triage_ctx["config"]
    clean_id = task_id.upper().replace("TASK-", "").zfill(4)
    refined_dir = cfg.backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    t = Task(id=clean_id, title=f"Feature {clean_id}", status="Refined", file_path=refined_dir / f"{clean_id}.md")
    write_task_file(t)
    triage_ctx["task_id"] = task_id


@given(parsers.parse('the worktree "{wt_path}" is preserved on branch "{branch}"'))
def worktree_preserved(triage_ctx: dict[str, Any], wt_path: str, branch: str):
    repo = triage_ctx["repo"]
    wt_dir = repo / wt_path.removeprefix("./")
    create_worktree(repo, branch=branch, worktree_dir=wt_dir)

    # Make parser.py 514 lines (+42 lines over 472 lines)
    parser_file = wt_dir / "src" / "spec_ops" / "core" / "parser.py"
    current_content = parser_file.read_text(encoding="utf-8").splitlines()
    extra_lines = [f"# extra line {i}" for i in range(514 - len(current_content))]
    parser_file.write_text("\n".join(current_content + extra_lines) + "\n", encoding="utf-8")

    # 2 more modified files + 1 untracked file to make: "3 modified files, 1 untracked file"
    mod1 = wt_dir / "src" / "spec_ops" / "core" / "mod1.py"
    mod1.write_text("x = 1\n", encoding="utf-8")
    mod2 = wt_dir / "src" / "spec_ops" / "core" / "mod2.py"
    mod2.write_text("y = 2\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/spec_ops/core/mod1.py", "src/spec_ops/core/mod2.py"], cwd=wt_dir, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add extra files"], cwd=wt_dir, capture_output=True)

    # Now modify them
    mod1.write_text("x = 100\n", encoding="utf-8")
    mod2.write_text("y = 200\n", encoding="utf-8")

    # Untracked file
    untracked = wt_dir / "untracked.py"
    untracked.write_text("z = 999\n", encoding="utf-8")

    # Diagnostics in .task-prompt.md
    prompt_file = wt_dir / ".task-prompt.md"
    prompt_file.write_text(
        "## Preflight Failure Feedback\n"
        "src/spec_ops/core/parser.py (514 lines > 500 limit)\n"
        "FAILED tests/test_parser.py::test_parse_syntax (AssertionError)\n"
        "uv.lock synchronized\n",
        encoding="utf-8",
    )
    triage_ctx["wt_dir"] = wt_dir


@when(parsers.parse('the engineer executes "{cmd}"'))
def engineer_executes_cmd(triage_ctx: dict[str, Any], cmd: str, capsys: pytest.CaptureFixture):
    cfg = triage_ctx["config"]
    parser = build_parser()
    parts = cmd.split()[1:]
    args = parser.parse_args(parts)
    code = handle_rescue_command(args, cfg)
    captured = capsys.readouterr()
    triage_ctx["stdout"] = captured.out
    triage_ctx["stderr"] = captured.err
    triage_ctx["exit_code"] = code


@then("the CLI displays a categorized diagnostic summary:")
def cli_displays_categorized_summary(triage_ctx: dict[str, Any]):
    stdout = triage_ctx["stdout"]
    assert "File Length Invariant" in stdout
    assert "src/spec_ops/core/parser.py (514 lines > 500 limit)" in stdout
    assert "Test Suite" in stdout
    assert "tests/test_parser.py::test_parse_syntax (AssertionError)" in stdout
    assert "Lockfile Integrity" in stdout
    assert "uv.lock synchronized" in stdout
    assert "Working Tree State" in stdout
    assert "3 modified files, 1 untracked file" in stdout


@then(parsers.parse('the CLI presents an interactive triage menu with options: "{menu_options}".'))
def cli_presents_interactive_menu(triage_ctx: dict[str, Any], menu_options: str):
    stdout = triage_ctx["stdout"]
    assert "Interactive triage menu with options: [d]iff, [p]atch, [s]hell, [r]eset, [c]omplete, [q]uit" in stdout


@given(parsers.parse('the engineer is in the interactive triage menu for "{task_id}"'))
def engineer_in_triage_menu(triage_ctx: dict[str, Any], task_id: str):
    worker_exhausted_attempts(triage_ctx, task_id, 3)
    clean_id = task_id.lower().replace("task-", "")
    worktree_preserved(triage_ctx, f".worktrees/task-{clean_id}", f"feat/{task_id}")


@when(parsers.parse('the engineer selects "[d]iff" and chooses "{rel_file}"'))
def engineer_selects_diff(triage_ctx: dict[str, Any], rel_file: str, capsys: pytest.CaptureFixture):
    cfg = triage_ctx["config"]
    task_id = triage_ctx.get("task_id", "TASK-0012")
    parser = build_parser()
    args = parser.parse_args(["rescue", "triage", task_id, "--action", "diff", "--file", rel_file])
    code = handle_rescue_command(args, cfg)
    captured = capsys.readouterr()
    triage_ctx["stdout"] = captured.out
    triage_ctx["exit_code"] = code


@then(parsers.parse('the CLI renders a syntax-highlighted diff comparing the worktree file against "{ref}"'))
def cli_renders_diff_against_head(triage_ctx: dict[str, Any], ref: str):
    stdout = triage_ctx["stdout"]
    assert "Syntax-highlighted diff comparing the worktree file against HEAD" in stdout


@then("displays the net line delta (+42 lines) and headroom to the 500-line invariant limit (-14 lines headroom, VIOLATION).")
def displays_net_line_delta_and_headroom(triage_ctx: dict[str, Any]):
    stdout = triage_ctx["stdout"]
    assert "Net line delta (+42 lines) and headroom to the 500-line invariant limit (-14 lines headroom, VIOLATION)." in stdout


@given("the failure breakdown indicates only file-length invariant violations with all tests passing")
def breakdown_only_file_length_violations(triage_ctx: dict[str, Any]):
    task_id = "TASK-0012"
    worker_exhausted_attempts(triage_ctx, task_id, 3)
    repo = triage_ctx["repo"]
    clean_id = task_id.lower().replace("task-", "")
    wt_dir = repo / ".worktrees" / f"task-{clean_id}"
    create_worktree(repo, branch=f"feat/{task_id}", worktree_dir=wt_dir)

    # 514 lines in parser.py
    parser_file = wt_dir / "src" / "spec_ops" / "core" / "parser.py"
    current_content = parser_file.read_text(encoding="utf-8").splitlines()
    extra_lines = [f"# extra line {i}" for i in range(514 - len(current_content))]
    parser_file.write_text("\n".join(current_content + extra_lines) + "\n", encoding="utf-8")

    # Tests passing feedback
    prompt_file = wt_dir / ".task-prompt.md"
    prompt_file.write_text(
        "## Preflight Failure Feedback\n"
        "src/spec_ops/core/parser.py (514 lines > 500 limit)\n"
        "all tests passed (100%)\n"
        "uv.lock synchronized\n",
        encoding="utf-8",
    )
    triage_ctx["wt_dir"] = wt_dir
    triage_ctx["task_id"] = task_id


@when("the triage analysis completes")
def triage_analysis_completes(triage_ctx: dict[str, Any], capsys: pytest.CaptureFixture):
    cfg = triage_ctx["config"]
    task_id = triage_ctx.get("task_id", "TASK-0012")
    parser = build_parser()
    args = parser.parse_args(["rescue", "triage", task_id])
    code = handle_rescue_command(args, cfg)
    captured = capsys.readouterr()
    triage_ctx["stdout"] = captured.out
    triage_ctx["exit_code"] = code


@then("the CLI outputs a targeted recommendation:")
def cli_outputs_targeted_recommendation(triage_ctx: dict[str, Any], docstring: str):
    stdout = triage_ctx["stdout"]
    assert docstring.strip() in stdout
