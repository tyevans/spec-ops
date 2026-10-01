"""Unit tests for worktree disk quota monitor and orphan prune daemon."""

from __future__ import annotations

import json
import os
import subprocess
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pytest

from spec_ops.backlog.queue import write_task_file
from spec_ops.cli.parser import build_parser
from spec_ops.cli.rescue_handler import handle_rescue_command
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.rescue.lifecycle import create_worktree
from spec_ops.rescue.prune_daemon import (
    DEFAULT_QUOTA_BYTES,
    QuotaAuditReport,
    WorktreeQuotaInfo,
    audit_worktree_quotas,
    check_worktree_merged_to_main,
    evaluate_prune_eligibility,
    find_task_status_and_history,
    format_quota_table,
    get_worktree_mtime,
    parse_duration,
    parse_threshold_bytes,
    run_prune,
)
from spec_ops.scaffold.init import init_project


def test_parse_duration_valid():
    assert parse_duration("7d") == timedelta(days=7)
    assert parse_duration("1day") == timedelta(days=1)
    assert parse_duration("2days") == timedelta(days=2)
    assert parse_duration("24h") == timedelta(hours=24)
    assert parse_duration("1hour") == timedelta(hours=1)
    assert parse_duration("30m") == timedelta(minutes=30)
    assert parse_duration("3600s") == timedelta(seconds=3600)
    assert parse_duration("2w") == timedelta(weeks=2)
    assert parse_duration("10") == timedelta(days=10)


def test_parse_duration_invalid():
    with pytest.raises(ValueError, match="Invalid duration format"):
        parse_duration("invalid")
    with pytest.raises(ValueError, match="Unsupported duration unit"):
        parse_duration("10xyz")


def test_parse_threshold_bytes():
    assert parse_threshold_bytes(None) == DEFAULT_QUOTA_BYTES
    assert parse_threshold_bytes(1024) == 1024
    assert parse_threshold_bytes("5GB") == 5 * 1024**3
    assert parse_threshold_bytes("1.5GB") == int(1.5 * 1024**3)
    assert parse_threshold_bytes("500MB") == 500 * 1024**2
    assert parse_threshold_bytes("100KB") == 100 * 1024
    assert parse_threshold_bytes("2048B") == 2048
    assert parse_threshold_bytes("bad") == DEFAULT_QUOTA_BYTES


def test_get_worktree_mtime(tmp_path: Path):
    wt_dir = tmp_path / "wt"
    wt_dir.mkdir()
    f1 = wt_dir / "a.py"
    f1.write_text("a")
    f2 = wt_dir / "b.py"
    f2.write_text("b")

    t_now = time.time()
    os.utime(f1, (t_now - 100, t_now - 100))
    os.utime(f2, (t_now, t_now))

    mtime = get_worktree_mtime(wt_dir)
    assert abs(mtime.timestamp() - t_now) < 1.0


def test_find_task_status_and_history(tmp_path: Path):
    backlog = tmp_path / "backlog"
    complete = backlog / "complete"
    refined = backlog / "refined"
    proposed = backlog / "proposed"
    for d in (complete, refined, proposed):
        d.mkdir(parents=True)

    # 1. Complete task without failure history
    (complete / "0001-test.md").write_text("---\nid: '0001'\ntitle: Test\n---\nBody\n")
    status, has_fail = find_task_status_and_history(backlog, "TASK-0001")
    assert status == "Complete"
    assert not has_fail

    # 2. Refined task with failure history
    (refined / "0002-failed.md").write_text(
        "---\nid: '0002'\nfailure_history:\n  - attempt: 1\n    reason: err\n---\nBody\n"
    )
    status, has_fail = find_task_status_and_history(backlog, "TASK-0002")
    assert status == "Refined"
    assert has_fail

    # 3. Proposed task
    (proposed / "0003-prop.md").write_text("---\nid: '0003'\n---\nBody\n")
    status, has_fail = find_task_status_and_history(backlog, "TASK-0003")
    assert status == "Proposed"
    assert not has_fail

    # 4. Orphan task
    status, has_fail = find_task_status_and_history(backlog, "TASK-9999")
    assert status == "Orphan"
    assert not has_fail


def test_format_quota_table():
    info = WorktreeQuotaInfo(
        worktree_name="task-0005",
        worktree_dir=Path("/fake/task-0005"),
        task_id="TASK-0005",
        task_status="Complete",
        size_bytes=1024 * 1024 * 100,
        last_modified=datetime.now(timezone.utc),
        last_modified_str="2026-10-01 10:00",
        is_dirty=False,
        is_merged=True,
        has_failure_history=False,
        branch="feat/TASK-0005",
        is_eligible=True,
    )
    report = QuotaAuditReport(
        worktrees=[info],
        total_size_bytes=1024 * 1024 * 100,
        threshold_bytes=DEFAULT_QUOTA_BYTES,
        threshold_exceeded=False,
        candidates_count=1,
        reclaimable_bytes=1024 * 1024 * 100,
        warning_message="",
    )
    rendered = format_quota_table(report)
    assert "Worktree Disk Quota & Storage Consumption" in rendered
    assert "task-0005" in rendered
    assert "Complete" in rendered
    assert "Yes (Candidate)" in rendered
    assert "100.0 MB" in rendered


def test_cli_rescue_quota_json(tmp_path: Path, capsys: pytest.CaptureFixture):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="RepoApp", target_dir=repo)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    cfg = load_config(repo)
    parser = build_parser()
    args = parser.parse_args(["rescue", "quota", "--json"])

    code = handle_rescue_command(args, cfg)
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert "worktrees" in data
    assert "total_size_bytes" in data
    assert "threshold_bytes" in data


def test_cli_rescue_prune_json(tmp_path: Path, capsys: pytest.CaptureFixture):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="RepoApp", target_dir=repo)
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@test.com"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    cfg = load_config(repo)
    parser = build_parser()
    args = parser.parse_args(["rescue", "prune", "--dry-run", "--json"])

    code = handle_rescue_command(args, cfg)
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["dry_run"] is True
    assert "pruned" in data
    assert "reclaimed_bytes" in data
