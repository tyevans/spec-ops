"""Integration tests for spec-ops queue tree, block, unblock, blockers, and spike create CLI commands."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from spec_ops.backlog.queue import write_task_file
from spec_ops.cli.main import main
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project


def setup_cli_repo(tmp_path: Path) -> Path:
    """Sets up a clean test repository with initialized SpecOps structure."""
    init_project(tmp_path, name="CliQueueTest")
    backlog_dir = tmp_path / "docs" / "project" / "backlog"
    proposed_dir = backlog_dir / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)

    t1 = Task(
        id="0001",
        title="Root Architecture",
        status="Complete",
        file_path=backlog_dir / "complete" / "0001-root.md",
    )
    (backlog_dir / "complete").mkdir(parents=True, exist_ok=True)
    write_task_file(t1)

    t2 = Task(
        id="0002",
        title="Downstream Feature",
        status="Proposed",
        dependencies=["TASK-0001"],
        file_path=proposed_dir / "0002-downstream.md",
    )
    write_task_file(t2)

    priority_file = backlog_dir / "PRIORITY.md"
    priority_file.write_text(
        "# Backlog Priority Index\n\n"
        "- **TASK-0001 (Complete)**: [`0001-root`](complete/0001-root.md)\n"
        "- **TASK-0002 (Proposed)**: [`0002-downstream`](proposed/0002-downstream.md)\n",
        encoding="utf-8",
    )
    return tmp_path


def test_cli_queue_tree_execution(tmp_path: Path, capsys):
    repo = setup_cli_repo(tmp_path)
    with (
        patch("os.getcwd", return_value=str(repo)),
        patch("pathlib.Path.cwd", return_value=repo),
    ):
        with patch("sys.argv", ["spec-ops", "queue", "tree"]):
            code = main()
            assert code == 0
            captured = capsys.readouterr().out
            assert "Execution Dependency Tree" in captured
            assert "TASK-0002" in captured


def test_cli_queue_tree_json(tmp_path: Path, capsys):
    repo = setup_cli_repo(tmp_path)
    with (
        patch("os.getcwd", return_value=str(repo)),
        patch("pathlib.Path.cwd", return_value=repo),
    ):
        with patch("sys.argv", ["spec-ops", "queue", "tree", "--json"]):
            code = main()
            assert code == 0
            out = capsys.readouterr().out
            data = json.loads(out)
            assert "waves" in data
            assert "tasks" in data
            assert "TASK-0002" in data["tasks"]


def test_cli_queue_tree_waves(tmp_path: Path, capsys):
    repo = setup_cli_repo(tmp_path)
    with (
        patch("os.getcwd", return_value=str(repo)),
        patch("pathlib.Path.cwd", return_value=repo),
    ):
        with patch("sys.argv", ["spec-ops", "queue", "tree", "--waves"]):
            code = main()
            assert code == 0
            out = capsys.readouterr().out
            assert "Delivery Horizons" in out or "Wave 0" in out


def test_cli_queue_block_unblock_and_blockers_flow(tmp_path: Path, capsys):
    repo = setup_cli_repo(tmp_path)
    with (
        patch("os.getcwd", return_value=str(repo)),
        patch("pathlib.Path.cwd", return_value=repo),
    ):
        # 1. Block task
        with patch(
            "sys.argv",
            [
                "spec-ops",
                "queue",
                "block",
                "TASK-0002",
                "--question",
                "Can SQLite handle concurrent workers?",
                "--type",
                "unknown",
                "--raised-by",
                "Riley",
            ],
        ):
            code = main()
            assert code == 0
            out = capsys.readouterr().out
            assert "marked as Blocked" in out

        # 2. Query blockers table
        with patch("sys.argv", ["spec-ops", "queue", "blockers"]):
            code = main()
            assert code == 0
            out = capsys.readouterr().out
            assert "TASK-0002" in out
            assert "SQLite" in out

        # 3. Query blockers json
        with patch("sys.argv", ["spec-ops", "queue", "blockers", "--json"]):
            code = main()
            assert code == 0
            out = capsys.readouterr().out
            b_list = json.loads(out)
            assert len(b_list) == 1
            assert b_list[0]["task_id"] == "TASK-0002"

        # 4. Tree displays blocked by unknown
        with patch("sys.argv", ["spec-ops", "queue", "tree"]):
            code = main()
            assert code == 0
            out = capsys.readouterr().out
            assert "BLOCKED: UNKNOWN" in out
            assert "Can SQLite handle concurrent workers?" in out

        # 5. Unblock task
        with patch(
            "sys.argv",
            [
                "spec-ops",
                "queue",
                "unblock",
                "TASK-0002",
                "--resolution",
                "Merge lock coordinates single-writer concurrency safely.",
                "--adr",
                "ADR-0010",
            ],
        ):
            code = main()
            assert code == 0
            out = capsys.readouterr().out
            assert "unblocked with resolution" in out
            assert "ADR-0010" in out

        # 6. Verify blockers list empty
        with patch("sys.argv", ["spec-ops", "queue", "blockers"]):
            code = main()
            assert code == 0
            out = capsys.readouterr().out
            assert "Zero active blockers" in out


def test_cli_spike_create(tmp_path: Path, capsys):
    repo = setup_cli_repo(tmp_path)
    with (
        patch("os.getcwd", return_value=str(repo)),
        patch("pathlib.Path.cwd", return_value=repo),
    ):
        with patch(
            "sys.argv",
            [
                "spec-ops",
                "spike",
                "create",
                "--name",
                "WebSocket Streaming Latency",
                "--question",
                "Measure p99 socket latency under 100 concurrent workers",
                "--timebox",
                "3h",
            ],
        ):
            code = main()
            assert code == 0
            out = capsys.readouterr().out
            assert "Scaffolded architectural spike" in out
            assert "Initialized test harness in spikes/spike_" in out
