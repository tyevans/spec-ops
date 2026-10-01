"""Unit tests for autonomous failure post-mortem clustering and prompt anti-loop synthesizer (US-0084, ADR-0020)."""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import pytest

from spec_ops.cli.main import main
from spec_ops.config.loader import load_config
from spec_ops.config.models import SpecOpsConfig
from spec_ops.core.models import Task
from spec_ops.rescue.failure_clustering import (
    ARCHETYPES,
    GENERIC_ARCHETYPE,
    ClusteredFailureEntry,
    FailureCluster,
    classify_failure_entry,
    cluster_failure_entries,
    collect_backlog_failures,
    format_fleet_failure_prompt,
    handle_cluster_cli,
    synthesize_fleet_negative_constraints,
)


def test_classify_failure_archetypes():
    """Verifies that failure entries are classified into their respective archetypes."""
    # Mock backdoors
    e1 = ClusteredFailureEntry(task_id="TASK-0001", reason="Prohibited mock backdoor in tests")
    assert classify_failure_entry(e1).archetype_id == "mock_backdoors"

    e1_inv = ClusteredFailureEntry(task_id="TASK-0001", reason="Failed check", failed_invariants=["ADR-0003"])
    assert classify_failure_entry(e1_inv).archetype_id == "mock_backdoors"

    # Line length
    e2 = ClusteredFailureEntry(task_id="TASK-0002", reason="Source file exceeds 500 lines limit")
    assert classify_failure_entry(e2).archetype_id == "line_length"

    e2_inv = ClusteredFailureEntry(task_id="TASK-0002", reason="Violated rule", failed_invariants=["ADR-0002"])
    assert classify_failure_entry(e2_inv).archetype_id == "line_length"

    # Credential leaks
    e3 = ClusteredFailureEntry(task_id="TASK-0003", reason="Detected exposed secret high-entropy token")
    assert classify_failure_entry(e3).archetype_id == "credential_leaks"

    e3_inv = ClusteredFailureEntry(task_id="TASK-0003", reason="Leak", failed_invariants=["ADR-0019"])
    assert classify_failure_entry(e3_inv).archetype_id == "credential_leaks"

    # Supply chain
    e4 = ClusteredFailureEntry(task_id="TASK-0004", reason="Unstaged uv.lock mutation and dependency drift")
    assert classify_failure_entry(e4).archetype_id == "supply_chain"

    e4_inv = ClusteredFailureEntry(task_id="TASK-0004", reason="Drift", failed_invariants=["ADR-0018"])
    assert classify_failure_entry(e4_inv).archetype_id == "supply_chain"

    # Dependency cycles
    e5 = ClusteredFailureEntry(task_id="TASK-0005", reason="Topological deadlock: dependency cycle detected by Tarjan")
    assert classify_failure_entry(e5).archetype_id == "dependency_cycles"

    e5_inv = ClusteredFailureEntry(task_id="TASK-0005", reason="Deadlock", failed_invariants=["ADR-0017"])
    assert classify_failure_entry(e5_inv).archetype_id == "dependency_cycles"

    # Generic fallback
    e6 = ClusteredFailureEntry(task_id="TASK-0006", reason="Unexpected timeout during execution")
    assert classify_failure_entry(e6).archetype_id == "generic_churn"


def test_cluster_failure_entries_aggregation():
    """Verifies clustering groups entries and computes correct task counts."""
    entries = [
        ClusteredFailureEntry(task_id="TASK-0001", reason="mock backdoor", failed_invariants=["ADR-0003"]),
        ClusteredFailureEntry(task_id="TASK-0001", reason="another mock error", failed_invariants=["ADR-0003"]),
        ClusteredFailureEntry(task_id="TASK-0002", reason="mock issue", failed_invariants=["ADR-0003"]),
        ClusteredFailureEntry(task_id="TASK-0003", reason="file length exceeds 500 lines"),
    ]
    clusters = cluster_failure_entries(entries, include_empty=False)
    assert len(clusters) == 2

    mock_cluster = next(c for c in clusters if c.archetype_id == "mock_backdoors")
    assert mock_cluster.count == 3
    assert set(mock_cluster.task_ids) == {"TASK-0001", "TASK-0002"}

    line_cluster = next(c for c in clusters if c.archetype_id == "line_length")
    assert line_cluster.count == 1
    assert line_cluster.task_ids == ["TASK-0003"]


def test_collect_backlog_failures_and_worktrees(tmp_path: Path):
    """Verifies collecting failure records across backlog files and worktree failure logs."""
    repo = tmp_path / "repo"
    backlog_dir = repo / "docs" / "project" / "backlog"
    (backlog_dir / "refined").mkdir(parents=True)
    (backlog_dir / "complete").mkdir(parents=True)

    # Task 1 in refined
    (backlog_dir / "refined" / "0010-task.md").write_text(
        "---\n"
        "id: '0010'\n"
        "title: Task Ten\n"
        "status: Refined\n"
        "failure_history:\n"
        "  - attempt_date: '2026-09-28'\n"
        '    reason: "Agent used mock backdoor violating ADR-0003"\n'
        "    failed_invariants: [ADR-0003]\n"
        "---\n# Body\n",
        encoding="utf-8",
    )

    # Task 2 in complete
    (backlog_dir / "complete" / "0020-task.md").write_text(
        "---\n"
        "id: '0020'\n"
        "title: Task Twenty\n"
        "status: Complete\n"
        "failure_history:\n"
        "  - attempt_date: '2026-09-27'\n"
        '    reason: "Secret leaked in commit violating ADR-0019"\n'
        "    failed_invariants: [ADR-0019]\n"
        "---\n# Body\n",
        encoding="utf-8",
    )

    # Worktree failure log
    wt_dir = repo / ".worktrees" / "task-0030"
    wt_dir.mkdir(parents=True)
    (wt_dir / ".failure.log").write_text("Dependency cycle deadlock detected", encoding="utf-8")

    # Worktree worker json
    wt_dir2 = repo / ".worktrees" / "task-0040"
    wt_dir2.mkdir(parents=True)
    (wt_dir2 / ".worker.json").write_text(json.dumps({"failure_log": "lockfile drift in uv.lock"}), encoding="utf-8")

    entries = collect_backlog_failures(backlog_dir, repo_root=repo)
    task_ids = {e.task_id for e in entries}
    assert "TASK-0010" in task_ids
    assert "TASK-0020" in task_ids
    assert "TASK-0030" in task_ids
    assert "TASK-0040" in task_ids


def test_synthesize_fleet_negative_constraints_formatting():
    """Verifies markdown formatting of synthesized prohibitions."""
    entries = [
        ClusteredFailureEntry(task_id="TASK-0024", reason="Agent attempted mock backdoor", failed_invariants=["ADR-0003"]),
    ]
    clusters = cluster_failure_entries(entries, include_empty=False)
    md = synthesize_fleet_negative_constraints(clusters)

    assert "## Prior Fleet Failures & Prohibitions" in md
    assert "Mock Backdoor Tampering (ADR-0003):" in md
    assert "Prohibition: Strictly forbidding mocks" in md
    assert "Fleet impact: Observed 1 failure(s) across tasks: TASK-0024." in md


def test_format_fleet_failure_prompt_prioritization():
    """Verifies that clusters matching task governing ADRs are sorted first."""
    clusters = [
        FailureCluster(
            archetype_id="line_length",
            name="Line Length",
            invariant_id="ADR-0002",
            mandate="Keep under 500 lines",
            prohibition="No large files",
            entries=[ClusteredFailureEntry(task_id="TASK-0001", reason="line length")],
        ),
        FailureCluster(
            archetype_id="mock_backdoors",
            name="Mock Backdoor Tampering",
            invariant_id="ADR-0003",
            mandate="Zero mocks",
            prohibition="No mocks",
            entries=[ClusteredFailureEntry(task_id="TASK-0002", reason="mock issue")],
        ),
    ]

    task = Task(
        id="0042",
        title="Test Task",
        status="Refined",
        target_bc="core",
        governing_adrs=["ADR-0003"],
    )

    prompt = format_fleet_failure_prompt(clusters, task=task)
    # Mock backdoor should be listed before line length because task cites ADR-0003
    mock_pos = prompt.find("Mock Backdoor Tampering")
    line_pos = prompt.find("Line Length")
    assert mock_pos != -1
    assert line_pos != -1
    assert mock_pos < line_pos


def test_handle_cluster_cli_json_and_human(tmp_path: Path, capsys: pytest.CaptureFixture):
    """Verifies handle_cluster_cli in both human and JSON formats."""
    repo = tmp_path / "repo"
    backlog_dir = repo / "docs" / "project" / "backlog"
    (backlog_dir / "refined").mkdir(parents=True)

    (backlog_dir / "refined" / "0024-mock-task.md").write_text(
        "---\n"
        "id: '0024'\n"
        "title: Mock Task\n"
        "status: Refined\n"
        "failure_history:\n"
        "  - attempt_date: '2026-09-29'\n"
        '    reason: "Agent used mock backdoor violating ADR-0003"\n'
        "    failed_invariants: [ADR-0003]\n"
        "---\n# Body\n",
        encoding="utf-8",
    )

    (repo / "specops.toml").write_text("[project]\nname = 'TestRepo'\n", encoding="utf-8")
    cfg = load_config(repo)

    # 1. Human format
    args_human = argparse.Namespace(json=False, task=None)
    ret = handle_cluster_cli(cfg, args_human)
    assert ret == 0
    out = capsys.readouterr().out
    assert "Fleet Failure Post-Mortem Clusters" in out
    assert "Mock Backdoor Tampering (ADR-0003)" in out
    assert "TASK-0024" in out

    # 2. JSON format
    args_json = argparse.Namespace(json=True, task=None)
    ret = handle_cluster_cli(cfg, args_json)
    assert ret == 0
    out_json = capsys.readouterr().out
    data = json.loads(out_json)
    assert data["total_failures"] == 1
    assert data["cluster_count"] == 1
    assert data["clusters"][0]["archetype_id"] == "mock_backdoors"

    # 3. Filter by task
    args_task = argparse.Namespace(json=True, task="TASK-0024")
    ret = handle_cluster_cli(cfg, args_task)
    assert ret == 0
    out_task = capsys.readouterr().out
    data_task = json.loads(out_task)
    assert data_task["total_failures"] == 1

    # 4. Filter by non-existent task
    args_empty = argparse.Namespace(json=False, task="TASK-9999")
    ret = handle_cluster_cli(cfg, args_empty)
    assert ret == 0
    out_empty = capsys.readouterr().out
    assert "No failure history records found for TASK-9999" in out_empty


def test_cli_rescue_cluster_frontdoor(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture):
    """Blackbox frontdoor verification: spec-ops rescue cluster through main() CLI entrypoint."""
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@test.com"], cwd=repo, check=True, capture_output=True)

    backlog_dir = repo / "docs" / "project" / "backlog"
    (backlog_dir / "refined").mkdir(parents=True)
    (repo / "specops.toml").write_text("[project]\nname = 'Test'\n", encoding="utf-8")
    (repo / "README.md").write_text("# Test\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True, capture_output=True)

    (backlog_dir / "refined" / "0024-task.md").write_text(
        "---\n"
        "id: '0024'\n"
        "title: Mock Task\n"
        "status: Refined\n"
        "failure_history:\n"
        "  - attempt_date: '2026-09-29'\n"
        '    reason: "Mock backdoor violating ADR-0003"\n'
        "    failed_invariants: [ADR-0003]\n"
        "---\n# Body\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(repo)

    # CLI test: spec-ops rescue cluster --json
    code = main(["rescue", "cluster", "--json"])
    assert code == 0
    captured = capsys.readouterr().out
    payload = json.loads(captured)
    assert payload["total_failures"] == 1
    assert payload["cluster_count"] == 1
    assert payload["clusters"][0]["archetype_id"] == "mock_backdoors"
