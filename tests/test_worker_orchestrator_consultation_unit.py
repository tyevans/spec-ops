"""Unit tests for multi-agent in-worktree worker orchestrator and specification consultation."""

from __future__ import annotations

import json
from pathlib import Path

from spec_ops.cli.main import build_parser, main
from spec_ops.cli.worker_handler import handle_worker_orchestrate
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.worker.commits import build_commit_trailers, format_task_commit_message
from spec_ops.worker.consultation import (
    ConsultedAdr,
    ConsultedPrd,
    ConsultedStory,
    PeerConsultationReview,
    SpecConsultationReport,
    WorkerOrchestrator,
    conduct_peer_consultation,
    consult_specifications,
)


def test_consult_specifications_real_repo():
    repo_root = Path(__file__).resolve().parent.parent
    task = Task(
        id="0114",
        title="Multi-Agent In-Worktree Implementation, Peer Consultation, and Verification Loop",
        governing_adrs=["ADR-0001", "ADR-0005"],
        governing_prds=["PRD-0006"],
        governing_stories=["US-0117"],
        target_bc="worker",
    )
    report = consult_specifications(task, repo_root)

    assert report.task_id == "TASK-0114"
    assert report.target_bc == "worker"
    assert len(report.adrs) == 2
    assert report.adrs[0].id == "ADR-0001"
    assert len(report.prds) == 1
    assert report.prds[0].id == "PRD-0006"
    assert len(report.stories) == 1
    assert report.stories[0].id == "US-0117"
    assert len(report.stories[0].scenarios) > 0
    assert "Specification Consultation Brief for TASK-0114" in report.brief

    data = report.to_dict()
    assert data["task_id"] == "TASK-0114"
    assert data["target_bc"] == "worker"
    assert len(data["adrs"]) == 2


def test_peer_consultation_compliant(tmp_path: Path):
    task = Task(id="0114", title="Worker Task", target_bc="worker")
    code_file = tmp_path / "src" / "spec_ops" / "worker" / "engine.py"
    code_file.parent.mkdir(parents=True, exist_ok=True)
    code_file.write_text("def run():\n    return True\n", encoding="utf-8")

    review = conduct_peer_consultation(
        task,
        tmp_path,
        tmp_path,
        check_git=False,
        changed_files=["src/spec_ops/worker/engine.py"],
    )
    assert review.approved is True
    assert len(review.seam_violations) == 0
    assert len(review.adr_violations) == 0


def test_peer_consultation_flags_backlog_modification(tmp_path: Path):
    task = Task(id="0114", title="Worker Task", target_bc="worker")
    review = conduct_peer_consultation(
        task,
        tmp_path,
        tmp_path,
        check_git=False,
        changed_files=["docs/project/backlog/refined/0114.md"],
    )
    assert review.approved is False
    assert any("ADR-0005" in err for err in review.adr_violations)
    assert any("Backlog files must not be touched" in fb for fb in review.feedback)


def test_peer_consultation_flags_seam_violation(tmp_path: Path):
    task = Task(id="0114", title="Worker Task", target_bc="worker")
    seam_file = tmp_path / "src" / "spec_ops" / "visualizer" / "export.py"
    seam_file.parent.mkdir(parents=True, exist_ok=True)
    seam_file.write_text("def export():\n    return ''\n", encoding="utf-8")

    review = conduct_peer_consultation(
        task,
        tmp_path,
        tmp_path,
        check_git=False,
        changed_files=["src/spec_ops/visualizer/export.py"],
    )
    assert review.approved is False
    assert any("Boundary seam crossing" in seam for seam in review.seam_violations)
    assert any("visualizer" in seam for seam in review.seam_violations)


def test_peer_consultation_flags_adr0002_file_length(tmp_path: Path):
    task = Task(id="0114", title="Worker Task", target_bc="worker")
    large_file = tmp_path / "src" / "spec_ops" / "worker" / "large.py"
    large_file.parent.mkdir(parents=True, exist_ok=True)
    large_file.write_text("\n".join(f"x_{i} = {i}" for i in range(505)), encoding="utf-8")

    review = conduct_peer_consultation(
        task,
        tmp_path,
        tmp_path,
        check_git=False,
        changed_files=["src/spec_ops/worker/large.py"],
    )
    assert review.approved is False
    assert any("ADR-0002" in err for err in review.adr_violations)


def test_peer_consultation_flags_adr0003_mock_backdoor(tmp_path: Path):
    task = Task(id="0114", title="Worker Task", target_bc="worker")
    test_file = tmp_path / "tests" / "test_something.py"
    test_file.parent.mkdir(parents=True, exist_ok=True)
    test_file.write_text("from unittest.mock import MagicMock\ndef test(): pass\n", encoding="utf-8")

    review = conduct_peer_consultation(
        task,
        tmp_path,
        tmp_path,
        check_git=False,
        changed_files=["tests/test_something.py"],
    )
    assert review.approved is False
    assert any("ADR-0003" in err for err in review.adr_violations)


def test_peer_consultation_flags_adr0010_hardcoded_secret(tmp_path: Path):
    task = Task(id="0114", title="Worker Task", target_bc="worker")
    sec_file = tmp_path / "src" / "spec_ops" / "worker" / "sec.py"
    sec_file.parent.mkdir(parents=True, exist_ok=True)
    fake_token = "ghp_" + "A" * 24 + "1234"
    sec_file.write_text(f"token = '{fake_token}'\n", encoding="utf-8")

    review = conduct_peer_consultation(
        task,
        tmp_path,
        tmp_path,
        check_git=False,
        changed_files=["src/spec_ops/worker/sec.py"],
    )
    assert review.approved is False
    assert any("ADR-0010" in err for err in review.adr_violations)


def test_worker_orchestrator_dry_run():
    repo_root = Path(__file__).resolve().parent.parent
    config = load_config(repo_root)
    orchestrator = WorkerOrchestrator(config, max_attempts=2, peer_review=True, dry_run=True)
    report = orchestrator.orchestrate(task_id="TASK-0114")

    assert report.success is True
    assert report.task_id == "TASK-0114"
    assert report.attempts == 1
    assert report.preflight_passed is True
    assert report.peer_review_passed is True
    assert report.specs_consulted is not None
    assert report.trailers["SpecOps-Task"] == "TASK-0114"
    assert report.trailers["SpecOps-Story"] == "US-0117"
    assert report.trailers["SpecOps-PRD"] == "PRD-0006"
    assert "ADR-0005" in report.trailers["SpecOps-ADR"]


def test_worker_orchestrator_missing_task():
    repo_root = Path(__file__).resolve().parent.parent
    config = load_config(repo_root)
    orchestrator = WorkerOrchestrator(config, max_attempts=2, dry_run=True)
    report = orchestrator.orchestrate(task_id="TASK-9999")

    assert report.success is False
    assert "not found" in report.message


def test_cli_parser_worker_orchestrate():
    parser = build_parser()
    args = parser.parse_args(["worker", "orchestrate", "TASK-0114", "--max-attempts", "4", "--no-peer-review", "--dry-run", "--json"])

    assert args.command == "worker"
    assert args.worker_action == "orchestrate"
    assert args.task_pos == "TASK-0114"
    assert args.max_attempts == 4
    assert args.peer_review is False
    assert args.dry_run is True
    assert args.json is True


def test_cli_worker_orchestrate_handler(capsys):
    repo_root = Path(__file__).resolve().parent.parent
    config = load_config(repo_root)
    parser = build_parser()
    args = parser.parse_args(["worker", "orchestrate", "TASK-0114", "--dry-run", "--json"])

    code = handle_worker_orchestrate(args, config)
    assert code == 0
    captured = capsys.readouterr()
    data = json.loads(captured.out)
    assert data["task_id"] == "TASK-0114"
    assert data["success"] is True
    assert data["trailers"]["SpecOps-Task"] == "TASK-0114"
    assert data["trailers"]["SpecOps-Story"] == "US-0117"
