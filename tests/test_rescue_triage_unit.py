"""Comprehensive unit tests for rescue triage and takeover to maximize mutmut kill rate."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import patch

import pytest

from spec_ops.backlog.queue import write_task_file
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.rescue.lifecycle import create_worktree
from spec_ops.rescue.triage import (
    CATEGORY_FILE_LENGTH,
    CATEGORY_GENERAL,
    CATEGORY_LOCKFILE,
    CATEGORY_SYNTAX_DEFECT,
    CATEGORY_TEST_SUITE,
    CATEGORY_WORKING_TREE,
    TriageFinding,
    analyze_worktree,
    calculate_file_diff,
    classify_log_snippet,
    format_triage_table,
    get_targeted_recommendation,
    parse_feedback_diagnostics,
    takeover_task,
)
from spec_ops.scaffold.init import init_project


@pytest.fixture
def unit_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="TriageUnitApp", target_dir=repo, profiles=["core", "bdd", "ddd"])

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Unit Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@specops.test"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)
    return repo


def test_classify_log_snippet_categories():
    assert classify_log_snippet("src/a.py (510 lines > 500 limit)") == CATEGORY_FILE_LENGTH
    assert classify_log_snippet("File length limit violated") == CATEGORY_FILE_LENGTH
    assert classify_log_snippet("exceeds file length boundary") == CATEGORY_FILE_LENGTH

    assert classify_log_snippet("SyntaxError: invalid syntax") == CATEGORY_SYNTAX_DEFECT
    assert classify_log_snippet("IndentationError: unexpected indent") == CATEGORY_SYNTAX_DEFECT
    assert classify_log_snippet("AST parse error in code") == CATEGORY_SYNTAX_DEFECT

    assert classify_log_snippet("FAILED tests/test_a.py::test_x - AssertionError") == CATEGORY_TEST_SUITE
    assert classify_log_snippet("def test_something():") == CATEGORY_TEST_SUITE
    assert classify_log_snippet("run pytest") == CATEGORY_TEST_SUITE

    assert classify_log_snippet("uv.lock drift detected") == CATEGORY_LOCKFILE
    assert classify_log_snippet("lockfile out of sync") == CATEGORY_LOCKFILE

    assert classify_log_snippet("3 modified files found") == CATEGORY_WORKING_TREE
    assert classify_log_snippet("1 untracked file") == CATEGORY_WORKING_TREE
    assert classify_log_snippet("working tree dirty") == CATEGORY_WORKING_TREE

    assert classify_log_snippet("random unrelated log message") == CATEGORY_GENERAL


def test_parse_feedback_diagnostics_empty():
    assert parse_feedback_diagnostics("") == []


def test_parse_feedback_diagnostics_all_cases():
    log = (
        "File length limit violated:\n"
        "src/core/parser.py (520 lines > 500 limit)\n"
        "File \"src/bad.py\", line 42\n"
        "  SyntaxError: invalid syntax\n"
        "src/inline.py:12: IndentationError: unindent does not match\n"
        "FAILED tests/test_unit.py::test_one - AssertionError\n"
        "FAILED tests/test_unit.py::test_two\n"  # duplicate test suite category should be ignored
    )
    findings = parse_feedback_diagnostics(log)
    assert len(findings) == 4

    fl = findings[0]
    assert fl.category == CATEGORY_FILE_LENGTH
    assert fl.status == "FAIL"
    assert fl.file_path == "src/core/parser.py"
    assert "520 lines > 500 limit" in fl.details

    st1 = findings[1]
    assert st1.category == CATEGORY_SYNTAX_DEFECT
    assert st1.status == "FAIL"
    assert st1.line_number == 42
    assert st1.file_path == "src/bad.py"

    st2 = findings[2]
    assert st2.category == CATEGORY_SYNTAX_DEFECT
    assert st2.line_number == 12
    assert st2.file_path == "src/inline.py"

    ts = findings[3]
    assert ts.category == CATEGORY_TEST_SUITE
    assert ts.status == "FAIL"
    assert "tests/test_unit.py::test_one" in ts.details


def test_analyze_worktree_file_length_on_disk(tmp_path: Path):
    wt = tmp_path / "wt_fl"
    wt.mkdir()
    big_file = wt / "big.py"
    big_file.write_text("\n".join(f"x = {i}" for i in range(505)) + "\n", encoding="utf-8")

    findings = analyze_worktree(wt, feedback_text="all tests passed")
    fl = next(f for f in findings if f.category == CATEGORY_FILE_LENGTH)
    assert fl.status == "FAIL"
    assert "big.py" in fl.details
    assert "505 lines > 500 limit" in fl.details

    ts = next(f for f in findings if f.category == CATEGORY_TEST_SUITE)
    assert ts.status == "PASS"

    lk = next(f for f in findings if f.category == CATEGORY_LOCKFILE)
    assert lk.status == "PASS"


def test_analyze_worktree_not_found(tmp_path: Path):
    ghost = tmp_path / "ghost_wt"
    findings = analyze_worktree(ghost, feedback_text="")
    wt_finding = next(f for f in findings if f.category == CATEGORY_WORKING_TREE)
    assert wt_finding.status == "CLEAN"
    assert "worktree not found" in wt_finding.details


def test_analyze_worktree_git_dirty_pluralization(unit_repo: Path):
    wt = unit_repo / ".worktrees" / "task-0001"
    create_worktree(unit_repo, branch="feat/TASK-0001", worktree_dir=wt)

    # 1 modified file
    tracked = wt / "tracked.py"
    tracked.write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "tracked.py"], cwd=wt, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add tracked"], cwd=wt, check=True, capture_output=True)
    tracked.write_text("x = 2\n", encoding="utf-8")

    # 1 untracked file
    (wt / "untracked.py").write_text("y = 3\n", encoding="utf-8")

    findings = analyze_worktree(wt, feedback_text="uv.lock drift detected")
    wt_state = next(f for f in findings if f.category == CATEGORY_WORKING_TREE)
    assert wt_state.status == "DIRTY"
    assert "1 modified file" in wt_state.details
    assert "1 untracked file" in wt_state.details

    lk = next(f for f in findings if f.category == CATEGORY_LOCKFILE)
    assert lk.status == "FAIL"
    assert "uv.lock drift detected" in lk.details


def test_format_triage_table():
    findings = [
        TriageFinding(category=CATEGORY_FILE_LENGTH, status="FAIL", details="parser.py (514 lines > 500 limit)"),
        TriageFinding(category=CATEGORY_TEST_SUITE, status="PASS", details="all tests passing"),
    ]
    table = format_triage_table(findings)
    assert "| Category" in table
    assert "| Status" in table
    assert "| Details" in table
    assert "| File Length Invariant" in table
    assert "| FAIL" in table
    assert "| Test Suite" in table
    assert "| PASS" in table


def test_get_targeted_recommendation():
    fl_fail = [
        TriageFinding(category=CATEGORY_FILE_LENGTH, status="FAIL", details="parser.py", file_path="src/parser.py"),
        TriageFinding(category=CATEGORY_TEST_SUITE, status="PASS", details="ok"),
    ]
    rec1 = get_targeted_recommendation(fl_fail, "TASK-0012")
    assert "Code passes tests but violates file limits" in rec1
    assert "decompose parser.py" in rec1

    ts_fail = [
        TriageFinding(category=CATEGORY_FILE_LENGTH, status="PASS", details="ok"),
        TriageFinding(category=CATEGORY_TEST_SUITE, status="FAIL", details="failed"),
    ]
    rec2 = get_targeted_recommendation(ts_fail, "TASK-0012")
    assert "Test failures detected" in rec2

    clean = [
        TriageFinding(category=CATEGORY_FILE_LENGTH, status="PASS", details="ok"),
        TriageFinding(category=CATEGORY_TEST_SUITE, status="PASS", details="ok"),
    ]
    rec3 = get_targeted_recommendation(clean, "TASK-0012")
    assert "Review diagnostics" in rec3


def test_calculate_file_diff(unit_repo: Path):
    wt = unit_repo / ".worktrees" / "task-0002"
    create_worktree(unit_repo, branch="feat/TASK-0002", worktree_dir=wt)

    target_file = wt / "src" / "service.py"
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text("class Base:\n    pass\n\ndef run():\n    return 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "src/service.py"], cwd=wt, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "add service"], cwd=wt, check=True, capture_output=True)

    # Modify: add a new class, modify run function
    target_file.write_text(
        "class Base:\n    pass\n\nclass NewClass:\n    pass\n\ndef run():\n    # modified\n    return 2\n",
        encoding="utf-8",
    )

    diff = calculate_file_diff(wt, "src/service.py")
    assert diff.file_path == "src/service.py"
    assert diff.net_delta > 0
    assert diff.headroom > 0
    assert diff.headroom_status == "COMPLIANT"
    assert "+ [class] NewClass" in diff.ast_diff_summary
    assert "+    return 2" in diff.diff_text

    # Test headroom warning boundary (e.g. 450 lines)
    target_file.write_text("\n".join(f"x = {i}" for i in range(450)) + "\n", encoding="utf-8")
    diff_warn = calculate_file_diff(wt, "src/service.py")
    assert diff_warn.headroom == 50
    assert diff_warn.headroom_status == "WARNING"

    # Test headroom violation boundary (e.g. 510 lines)
    target_file.write_text("\n".join(f"x = {i}" for i in range(510)) + "\n", encoding="utf-8")
    diff_viol = calculate_file_diff(wt, "src/service.py")
    assert diff_viol.headroom < 0
    assert diff_viol.headroom_status == "VIOLATION"


def test_takeover_task_nonexistent_and_success(unit_repo: Path):
    cfg = load_config(unit_repo)

    # Non-existent task fails
    ok, msg = takeover_task(cfg, "TASK-9999")
    assert not ok
    assert "not found in backlog" in msg

    # Create task in refined
    refined_dir = cfg.backlog_dir / "refined"
    refined_dir.mkdir(parents=True, exist_ok=True)
    t = Task(id="0044", title="Takeover Task", status="Refined", file_path=refined_dir / "0044.md")
    write_task_file(t)

    # Takeover provisions worktree and sets claim
    ok, msg = takeover_task(cfg, "TASK-0044", claimant="riley_tester")
    assert ok
    assert "claim transferred to human developer: riley_tester" in msg
    assert (unit_repo / ".worktrees" / "task-0044").exists()

    reloaded_task = (refined_dir / "0044.md").read_text(encoding="utf-8")
    assert "claimed_by: riley_tester" in reloaded_task


def test_rescue_cli_handler_actions(unit_repo: Path, capsys: pytest.CaptureFixture):
    from spec_ops.cli.parser import build_parser
    from spec_ops.cli.rescue_handler import handle_rescue_command

    cfg = load_config(unit_repo)
    parser = build_parser()

    # Non-existent worktree
    args = parser.parse_args(["rescue", "inspect", "TASK-0099"])
    code = handle_rescue_command(args, cfg)
    assert code == 1
    assert "No worktree found for TASK-0099" in capsys.readouterr().out

    args_triage = parser.parse_args(["rescue", "triage", "TASK-0099"])
    code = handle_rescue_command(args_triage, cfg)
    assert code == 1

    args_shell = parser.parse_args(["rescue", "shell", "TASK-0099"])
    code = handle_rescue_command(args_shell, cfg)
    assert code == 1

    # Create worktree
    wt = unit_repo / ".worktrees" / "task-0099"
    create_worktree(unit_repo, branch="feat/TASK-0099", worktree_dir=wt)

    # Shell
    args_shell_ok = parser.parse_args(["rescue", "shell", "TASK-0099"])
    assert handle_rescue_command(args_shell_ok, cfg) == 0
    assert "Entering shell for TASK-0099" in capsys.readouterr().out

    # Inspect
    args_inspect = parser.parse_args(["rescue", "inspect", "TASK-0099"])
    assert handle_rescue_command(args_inspect, cfg) == 0
    out = capsys.readouterr().out
    assert "=== Stalled Worktree: TASK-0099 ===" in out
    assert "feat/TASK-0099" in out

    # Triage
    args_tr = parser.parse_args(["rescue", "triage", "TASK-0099"])
    assert handle_rescue_command(args_tr, cfg) == 0
    out_tr = capsys.readouterr().out
    assert "Categorized Diagnostic Summary:" in out_tr
