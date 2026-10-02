"""BDD step definitions for US-0090: Preserved Worktree AI-to-Human Handover Brief and Debug Cheatsheet."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.backlog.queue import write_task_file
from spec_ops.worker import BacklogWorkerEngine
from spec_ops.cli.parser import build_parser
from spec_ops.cli.rescue_handler import handle_rescue_command
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.rescue.handover import generate_handover_brief
from spec_ops.rescue.lifecycle import create_worktree
from spec_ops.scaffold.init import init_project

scenarios("features/us_0090_preserved_worktree_ai_to_human_handover_brief.feature")


@pytest.fixture
def bdd_us90_ctx(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()

    init_project(name="RescueApp", target_dir=repo, profiles=["core", "bdd", "ddd"])

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Riley Developer"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "riley@specops.test"], cwd=repo, check=True, capture_output=True)

    # Initial codebase
    src_file = repo / "src" / "curator.py"
    src_file.parent.mkdir(parents=True, exist_ok=True)
    src_file.write_text("def buffer_sync():\n    return False\n", encoding="utf-8")

    test_file = repo / "tests" / "test_curator.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("def test_buffer_sync():\n    from curator import buffer_sync\n    assert buffer_sync() is True\n", encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    cfg = load_config(repo)
    cfg.quality.preflight = []
    cfg.execution.agent_max_attempts = 3
    return {"repo": repo, "config": cfg}


# --- Scenario 1: Automatic generation of HANDOVER.md upon agent exhaustion ---


@given(parsers.parse('an autonomous worker exhausts max attempts on "{task_id}"'))
def worker_exhausts_attempts(bdd_us90_ctx: dict[str, Any], task_id: str):
    cfg = bdd_us90_ctx["config"]
    repo = bdd_us90_ctx["repo"]
    clean_id = task_id.upper().replace("TASK-", "").zfill(4)

    refined_dir = cfg.backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    t = Task(
        id=clean_id,
        title="Curator Buffer Synchronization",
        status="Refined",
        target_bc="rescue",
        governing_prds=["PRD-0004"],
        governing_stories=["US-0090"],
        governing_adrs=["ADR-0001", "ADR-0002", "ADR-0003"],
        file_path=refined_dir / f"{clean_id}.md",
    )
    write_task_file(t)
    bdd_us90_ctx["task"] = t
    bdd_us90_ctx["task_id"] = task_id

    wt_dir = repo / ".worktrees" / f"task-{clean_id.lower()}"
    create_worktree(repo, branch=f"feat/TASK-{clean_id}", worktree_dir=wt_dir)
    bdd_us90_ctx["wt_dir"] = wt_dir


@when(parsers.parse('the worker engine halts and preserves the worktree at "{wt_path}"'))
def worker_halts_and_preserves(bdd_us90_ctx: dict[str, Any], wt_path: str):
    wt_dir = bdd_us90_ctx["wt_dir"]
    task = bdd_us90_ctx["task"]
    cfg = bdd_us90_ctx["config"]

    failure_log = (
        "Traceback (most recent call last):\n"
        "  File 'tests/test_curator.py', line 3, in test_buffer_sync\n"
        "    assert buffer_sync() is True\n"
        "FAILED tests/test_curator.py::test_buffer_sync - AssertionError: assert False is True"
    )

    # Trigger handover generation
    generate_handover_brief(
        worktree_dir=wt_dir,
        task=task,
        failure_log=failure_log,
        config=cfg,
    )
    bdd_us90_ctx["failure_log"] = failure_log


@then(parsers.parse('a structured handover document "{handover_path}" is generated containing:'))
def verify_handover_document_sections(bdd_us90_ctx: dict[str, Any], handover_path: str):
    repo = bdd_us90_ctx["repo"]
    target_file = repo / handover_path.removeprefix("./")
    assert target_file.exists(), f"Expected {target_file} to exist."

    content = target_file.read_text(encoding="utf-8")
    assert "## Task Header" in content
    assert "TASK-0014" in content
    assert "Curator Buffer Synchronization" in content
    assert "rescue" in content

    assert "## Attempt Timeline" in content
    assert "Attempt 1" in content
    assert "Attempt 2" in content
    assert "Attempt 3" in content
    assert "exit code" in content.lower()

    assert "## Exact Failure Log" in content
    assert "FAILED tests/test_curator.py::test_buffer_sync" in content

    assert "## Governing Context" in content
    assert "[PRD-0004]" in content
    assert "[US-0090]" in content
    assert "[ADR-0001]" in content

    assert "## Reproduction Command" in content
    assert "uv run pytest tests/test_curator.py -k test_buffer_sync" in content

    assert "## Completion Command" in content
    assert "spec-ops rescue TASK-0014 --complete" in content


# --- Scenario 2: Terminal cheatsheet display upon running rescue inspection ---


@given(parsers.parse('an engineer runs "{cmd}"'))
def engineer_runs_inspection(bdd_us90_ctx: dict[str, Any], cmd: str, capsys: pytest.CaptureFixture):
    cfg = bdd_us90_ctx["config"]
    repo = bdd_us90_ctx["repo"]

    parts = cmd.split()[1:]
    tid = parts[1] if len(parts) > 1 and parts[1] != "inspect" else (parts[2] if len(parts) > 2 else "TASK-0014")

    clean_id = tid.upper().replace("TASK-", "").zfill(4)
    wt_dir = repo / ".worktrees" / f"task-{clean_id.lower()}"
    if not wt_dir.exists():
        create_worktree(repo, branch=f"feat/TASK-{clean_id}", worktree_dir=wt_dir)
        refined_dir = cfg.backlog_dir / "refined"
        refined_dir.mkdir(parents=True, exist_ok=True)
        t = Task(
            id=clean_id,
            title="Curator Buffer Synchronization",
            status="Refined",
            target_bc="rescue",
            file_path=refined_dir / f"{clean_id}.md",
        )
        write_task_file(t)
        generate_handover_brief(
            worktree_dir=wt_dir,
            task=t,
            failure_log="FAILED tests/test_curator.py::test_buffer_sync - AssertionError",
            config=cfg,
        )

    parser = build_parser()
    args = parser.parse_args(parts)
    handle_rescue_command(args, cfg)
    captured = capsys.readouterr()
    bdd_us90_ctx["terminal_output"] = captured.out


@when("the worktree metadata is displayed")
def worktree_metadata_is_displayed(bdd_us90_ctx: dict[str, Any]):
    out = bdd_us90_ctx["terminal_output"]
    assert "=== Stalled Worktree:" in out
    assert "Directory:" in out


@then("the terminal renders a copy-paste developer cheatsheet:")
def terminal_renders_cheatsheet(bdd_us90_ctx: dict[str, Any]):
    out = bdd_us90_ctx["terminal_output"]
    assert "🚀 Rescue Quickstart:" in out
    assert "1. Jump into worktree:  cd .worktrees/task-0014" in out
    assert "2. Reproduce failure:   uv run pytest tests/test_curator.py -k test_buffer_sync" in out
    assert "3. Inspect changes:     git diff HEAD" in out
    assert "4. Complete & merge:    spec-ops rescue TASK-0014 --complete" in out
    assert "5. Discard & reset:     spec-ops rescue reset TASK-0014" in out


# --- Scenario 3: Ensuring HANDOVER.md is excluded from production commits ---


@given(parsers.parse('the engineer has resolved the bug inside "{wt_path}"'))
def engineer_resolved_bug(bdd_us90_ctx: dict[str, Any], wt_path: str):
    repo = bdd_us90_ctx["repo"]
    wt_dir = repo / wt_path.removeprefix("./")
    clean_id = wt_dir.name.split("-")[-1]
    tid = f"TASK-{clean_id.zfill(4)}"

    if not wt_dir.exists():
        create_worktree(repo, branch=f"feat/TASK-{clean_id.zfill(4)}", worktree_dir=wt_dir)

    cfg = bdd_us90_ctx["config"]
    refined_dir = cfg.backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    task_file = refined_dir / f"{clean_id.zfill(4)}.md"
    if not task_file.exists():
        t = Task(
            id=clean_id.zfill(4),
            title="Curator Buffer Synchronization",
            status="Refined",
            target_bc="rescue",
            file_path=task_file,
        )
        write_task_file(t)

    # Ensure HANDOVER.md exists in worktree
    (wt_dir / "HANDOVER.md").write_text("# Ephemeral Handover\n", encoding="utf-8")
    (wt_dir / ".task-prompt.md").write_text("# Ephemeral Prompt\n", encoding="utf-8")

    # Fix the code
    src_file = wt_dir / "src" / "curator.py"
    src_file.write_text("def buffer_sync():\n    return True\n", encoding="utf-8")

    bdd_us90_ctx["wt_dir"] = wt_dir
    bdd_us90_ctx["task_id"] = tid


@when(parsers.parse('the engineer executes "{cmd}"'))
def engineer_executes_complete_rescue(bdd_us90_ctx: dict[str, Any], cmd: str, capsys: pytest.CaptureFixture):
    cfg = bdd_us90_ctx["config"]
    parser = build_parser()
    parts = cmd.split()[1:]
    args = parser.parse_args(parts)
    code = handle_rescue_command(args, cfg)
    captured = capsys.readouterr()
    bdd_us90_ctx["complete_exit_code"] = code
    bdd_us90_ctx["complete_output"] = captured.out
    assert code == 0, f"Expected 0 exit code, got {code}:\n{captured.out}\n{captured.err}"


@then(parsers.parse('"{file_a}" and "{file_b}" are automatically purged prior to git staging'))
def files_automatically_purged(bdd_us90_ctx: dict[str, Any], file_a: str, file_b: str):
    wt_dir = bdd_us90_ctx["wt_dir"]
    # Even if worktree directory was pruned or still exists, neither file should exist
    assert not (wt_dir / file_a).exists()
    assert not (wt_dir / file_b).exists()


@then(parsers.parse('zero ephemeral handover artifacts are committed to "{branch}".'))
def zero_ephemeral_committed(bdd_us90_ctx: dict[str, Any], branch: str):
    repo = bdd_us90_ctx["repo"]
    log_res = subprocess.run(
        ["git", "log", branch, "--name-only", "--pretty=format:"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    committed_files = [f.strip() for f in log_res.stdout.splitlines() if f.strip()]
    assert "HANDOVER.md" not in committed_files, f"HANDOVER.md unexpectedly found in commits: {committed_files}"
    assert ".task-prompt.md" not in committed_files, f".task-prompt.md unexpectedly found in commits: {committed_files}"
