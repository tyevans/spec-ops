"""Unit tests for cryptographic worker integration gates and signing helpers."""

from __future__ import annotations

import subprocess
from pathlib import Path

from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.config.models import ComplianceSettings, SecuritySettings, SpecOpsConfig
from spec_ops.core.models import Task
from spec_ops.security.dual_custody import (
    record_sign_off,
    sign_task_review,
    verify_worker_integration_gates,
)
from spec_ops.security.signing import (
    format_commit_message,
    load_authorized_signers,
    validate_key_id,
    verify_branch_commit_signatures,
)


def test_verify_worker_integration_gates(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    (repo / "f.txt").write_text("base", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "main"], cwd=repo, check=True)

    subprocess.run(["git", "checkout", "-b", "feat/test"], cwd=repo, check=True)
    (repo / "f2.txt").write_text("feature", encoding="utf-8")
    subprocess.run(["git", "add", "f2.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "feature commit"], cwd=repo, check=True)

    task = Task(id="0001", title="Task 1", claimed_by="worker-1")
    cfg = SpecOpsConfig(
        root_dir=repo,
        security=SecuritySettings(compliance=ComplianceSettings(require_signed_commits=True)),
    )

    # Fails due to unsigned commit
    ok, msg = verify_worker_integration_gates(repo, "feat/test", task, cfg)
    assert ok is False
    assert "Compliance Violation: Commit" in msg

    # When require_signed_commits is False, fails due to dual custody
    cfg_nosig = SpecOpsConfig(root_dir=repo)
    ok, msg = verify_worker_integration_gates(repo, "feat/test", task, cfg_nosig)
    assert ok is False
    assert "Dual-Custody Gate:" in msg

    # When signed off, passes
    task.signed_off_by = "Riley <riley@example.com>"
    ok, msg = verify_worker_integration_gates(repo, "feat/test", task, cfg_nosig)
    assert ok is True
    assert msg == "All integration gates passed."


def test_sign_task_review_numeric_id_and_default_repo(tmp_path: Path):
    refined = tmp_path / "docs" / "project" / "backlog" / "refined"
    refined.mkdir(parents=True)
    t_file = refined / "0042-task.md"
    task = Task(id="0042", title="Task 42", status="Refined", file_path=t_file)
    write_task_file(task)

    config = SpecOpsConfig(
        root_dir=tmp_path,
        security=SecuritySettings(
            compliance=ComplianceSettings(authorized_signers=["Riley <riley@example.com>"])
        ),
    )

    # Test numeric ID "42" normalization
    ok, msg = sign_task_review("42", "Riley <riley@example.com>", config)
    assert ok is True
    assert "TASK-0042" in msg
    loaded_tasks = BacklogQueue(config.backlog_dir).list_all_tasks()
    assert loaded_tasks[0].signed_off_by == "Riley <riley@example.com>"


def test_record_sign_off_default_timestamp_and_no_file():
    task = Task(id="0001", title="Task 1")
    record_sign_off(task, "Riley <riley@example.com>")
    assert task.signed_off_by == "Riley <riley@example.com>"
    assert task.signed_off_at != ""
    assert "T" in task.signed_off_at


def test_validate_key_id_lengths_and_ssh():
    assert validate_key_id("12345678") is True
    assert validate_key_id("1234567890abcdef") is True
    assert validate_key_id("a" * 40) is True
    assert validate_key_id("f" * 64) is True
    assert validate_key_id("1234567890") is False
    assert validate_key_id("ecdsa-sha2-nistp256 AAAAE2VjZHNh...") is True


def test_format_commit_message_tuples_and_existing_merge():
    formatted = format_commit_message("Subject", [("SpecOps-Task", "TASK-0001")])
    assert "SpecOps-Task: TASK-0001" in formatted

    existing_msg = "Subject\n\nSpecOps-Task: TASK-0001\n"
    formatted2 = format_commit_message(existing_msg, {"SpecOps-Signed-By": "Riley <riley@example.com>"})
    assert "SpecOps-Task: TASK-0001" in formatted2
    assert "SpecOps-Signed-By: Riley <riley@example.com>" in formatted2


def test_verify_branch_commit_signatures_defaults_and_u_status(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    (repo / "f.txt").write_text("main", encoding="utf-8")
    subprocess.run(["git", "add", "f.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "main"], cwd=repo, check=True)

    ok, sha, msg = verify_branch_commit_signatures(repo)
    assert ok is True
    assert sha is None


def test_load_authorized_signers_fallback_allowed_signers(tmp_path: Path):
    allowed_file = tmp_path / ".allowed_signers"
    allowed_file.write_text("alex@example.com ssh-ed25519 AAAAC3...\n", encoding="utf-8")
    config = SpecOpsConfig(root_dir=tmp_path)
    signers = load_authorized_signers(config=config, repo_dir=tmp_path)
    assert "alex@example.com" in signers
