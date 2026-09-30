"""Unit and mutation kill test suite for cryptographic signing and dual-custody verification."""

from __future__ import annotations

import subprocess
from pathlib import Path

from spec_ops.config.models import ComplianceSettings, SecuritySettings, SpecOpsConfig
from spec_ops.core.models import Task
from spec_ops.security.dual_custody import (
    evaluate_dual_custody_gate,
    is_autonomous_task,
    record_sign_off,
    sign_task_review,
    verify_worker_integration_gates,
)
from spec_ops.security.signing import (
    extract_email,
    format_commit_message,
    load_authorized_signers,
    parse_git_trailers,
    validate_key_id,
    verify_branch_commit_signatures,
    verify_reviewer_identity,
)


def test_validate_key_id_comprehensive():
    # Non-string inputs
    assert validate_key_id(12345) is False  # type: ignore
    assert validate_key_id(None) is False  # type: ignore
    assert validate_key_id(["key"]) is False  # type: ignore

    # Length boundaries
    assert validate_key_id("") is False
    assert validate_key_id("   ") is False
    assert validate_key_id("ab") is False
    assert validate_key_id("abc") is False  # not valid key format

    # Forbidden characters
    assert validate_key_id("Riley\n<riley@example.com>") is False
    assert validate_key_id("Riley\r<riley@example.com>") is False
    assert validate_key_id("Riley\0<riley@example.com>") is False
    assert validate_key_id("Riley;<riley@example.com>") is False

    # Valid GPG key IDs (8 or 16 hex chars)
    assert validate_key_id("12345678") is True
    assert validate_key_id("0x12345678") is True
    assert validate_key_id("1234567890ABCDEF") is True
    assert validate_key_id("0x1234567890abcdef") is True
    assert validate_key_id("1234567") is False
    assert validate_key_id("123456789") is False

    # Valid GPG Fingerprints (40 or 64 hex chars)
    assert validate_key_id("a" * 40) is True
    assert validate_key_id("0x" + "b" * 40) is True
    assert validate_key_id("c" * 64) is True
    assert validate_key_id("d" * 50) is False

    # Length limit > 256
    too_long = "a" * 245 + "@example.com"  # len > 256
    assert len(too_long) > 256
    assert validate_key_id(too_long) is False

    # Valid RFC 2822
    assert validate_key_id("user@domain.com") is True
    assert validate_key_id("User <user@domain.com>") is True
    assert validate_key_id("Alice Architect <alice@domain.com>") is True

    # Valid SSH key formats
    assert validate_key_id("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIG5... user@host") is True
    assert validate_key_id("ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABAQ... comment") is True
    assert validate_key_id("ecdsa-sha2-nistp256 AAAAE2VjZHNh... key") is True
    assert validate_key_id("SHA256:abcd1234efgh5678ijkl") is True


def test_format_commit_message_comprehensive():
    # Existing trailers stripped from body and deduplicated
    orig = (
        "Feat: Add security gate\n\n"
        "Detailed explanation here.\n\n"
        "SpecOps-Task: TASK-0001\n"
        "Signed-off-by: Alice <alice@example.com>\n"
    )
    res = format_commit_message(
        orig,
        [("SpecOps-Signed-By", "Bob <bob@example.com>")],
    )
    assert "Feat: Add security gate" in res
    assert "Detailed explanation here." in res
    assert res.count("SpecOps-Task: TASK-0001") == 1
    assert res.count("Signed-off-by: Alice <alice@example.com>") == 1
    assert res.count("SpecOps-Signed-By: Bob <bob@example.com>") == 1

    # Empty trailer value ignored
    res_empty_val = format_commit_message("Subject", {"Empty": "", "Valid": "val"})
    assert "Empty:" not in res_empty_val
    assert "Valid: val" in res_empty_val

    # Trailers with continuation lines
    orig_cont = (
        "Commit Title\n\n"
        "Body paragraph\n\n"
        "X-Custom: line1\n"
        "  continuation line\n"
    )
    res_cont = format_commit_message(orig_cont, [("New-Key", "New-Val")])
    assert res_cont.count("X-Custom: line1") == 1
    assert "New-Key: New-Val" in res_cont


def test_load_authorized_signers_configurations(tmp_path: Path):
    # 1. Config is None
    signers = load_authorized_signers(config=None, repo_dir=tmp_path)
    assert signers == set()

    # 2. Config with security=None
    cfg_no_sec = SpecOpsConfig(root_dir=tmp_path, security=None)  # type: ignore
    assert load_authorized_signers(config=cfg_no_sec, repo_dir=tmp_path) == set()

    # 3. Config with compliance=None
    cfg_no_comp = SpecOpsConfig(root_dir=tmp_path, security=SecuritySettings(compliance=None))  # type: ignore
    assert load_authorized_signers(config=cfg_no_comp, repo_dir=tmp_path) == set()

    # 4. Config with empty allowed_signers_file
    cfg_empty_file = SpecOpsConfig(
        root_dir=tmp_path,
        security=SecuritySettings(
            compliance=ComplianceSettings(
                authorized_signers=["  ALICE <ALICE@EXAMPLE.COM>  "],
                allowed_signers_file="",
            )
        ),
    )
    signers = load_authorized_signers(config=cfg_empty_file, repo_dir=tmp_path)
    assert "alice <alice@example.com>" in signers
    assert "alice@example.com" in signers

    # 5. repo_dir is None falls back to config.root_dir
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir(parents=True, exist_ok=True)
    (ssh_dir / "allowed_signers").write_text("bob@example.com ssh-ed25519 AAA...\n", encoding="utf-8")
    cfg_root = SpecOpsConfig(root_dir=tmp_path)
    signers_root = load_authorized_signers(config=cfg_root, repo_dir=None)
    assert "bob@example.com" in signers_root

    # 6. .allowed_signers in repo root
    tmp_sub = tmp_path / "sub"
    tmp_sub.mkdir()
    (tmp_sub / ".allowed_signers").write_text("charlie@example.com ssh-rsa AAA...\n", encoding="utf-8")
    signers_sub = load_authorized_signers(config=None, repo_dir=tmp_sub)
    assert "charlie@example.com" in signers_sub


def test_verify_reviewer_identity_edge_cases(tmp_path: Path):
    cfg = SpecOpsConfig(
        root_dir=tmp_path,
        security=SecuritySettings(
            compliance=ComplianceSettings(authorized_signers=["Riley <riley@example.com>"])
        ),
    )
    # Match by email only
    ok, msg = verify_reviewer_identity("riley@example.com", config=cfg, repo_dir=tmp_path)
    assert ok is True

    # Match case-insensitively
    ok, msg = verify_reviewer_identity("RILEY <riley@EXAMPLE.com>", config=cfg, repo_dir=tmp_path)
    assert ok is True

    # Invalid key id format
    ok, msg = verify_reviewer_identity("bad;id", config=cfg, repo_dir=tmp_path)
    assert ok is False
    assert "Invalid identity format" in msg

    # Unauthorized identity
    ok, msg = verify_reviewer_identity("Eve <eve@bad.com>", config=cfg, repo_dir=tmp_path)
    assert ok is False
    assert "not in authorized signers keyring" in msg

    # No keyring configured -> allows any valid format
    cfg_open = SpecOpsConfig(root_dir=tmp_path)
    ok, msg = verify_reviewer_identity("Dev <dev@test.com>", config=cfg_open, repo_dir=tmp_path)
    assert ok is True


def test_verify_branch_commit_signatures_cases(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)

    (repo / "f1.txt").write_text("main", encoding="utf-8")
    subprocess.run(["git", "add", "f1.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "main initial"], cwd=repo, check=True)

    subprocess.run(["git", "checkout", "-b", "feat/sub"], cwd=repo, check=True)
    (repo / "f2.txt").write_text("feat", encoding="utf-8")
    subprocess.run(["git", "add", "f2.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "feat commit"], cwd=repo, check=True)

    # 1. Test with default base_branch="main" and explicit target_branch
    ok, sha, msg = verify_branch_commit_signatures(repo, target_branch="feat/sub")
    assert ok is False
    assert sha is not None
    assert "Compliance Violation: Commit" in msg

    # 2. Test with default target_branch=None (which resolves to HEAD)
    ok_head, sha_head, msg_head = verify_branch_commit_signatures(repo)
    assert ok_head is False
    assert sha_head == sha

    # 3. Test on main branch (no commits ahead of main)
    subprocess.run(["git", "checkout", "main"], cwd=repo, check=True)
    ok_main, sha_main, msg_main = verify_branch_commit_signatures(repo, base_branch="main")
    assert ok_main is True
    assert sha_main is None
    assert "No commits to verify." in msg_main


def test_dual_custody_gate_with_compliance_config():
    # Non-autonomous task without claims
    task = Task(id="0001", title="Task 1", claimed_by="", signed_off_by="")
    # When dual_custody=True is configured, non-autonomous tasks are treated as requiring dual custody
    cfg = SpecOpsConfig(
        security=SecuritySettings(compliance=ComplianceSettings(dual_custody=True))
    )
    ok, msg = evaluate_dual_custody_gate(task, config=cfg)
    assert ok is False
    assert "Dual-Custody Gate:" in msg

    # Passing config=None does NOT trigger dual custody for non-autonomous task
    ok_none, _ = evaluate_dual_custody_gate(task, config=None)
    assert ok_none is True


def test_record_sign_off_utc_timestamp():
    task = Task(id="0001", title="Task 1")
    record_sign_off(task, "Reviewer <rev@example.com>")
    assert task.signed_off_by == "Reviewer <rev@example.com>"
    assert "+00:00" in task.signed_off_at or task.signed_off_at.endswith("Z")


def test_sign_task_review_clean_ids(tmp_path: Path):
    refined = tmp_path / "docs" / "project" / "backlog" / "refined"
    refined.mkdir(parents=True)
    t_file = refined / "0099-task.md"
    task = Task(id="0099", title="Task 99", status="Refined", file_path=t_file)
    from spec_ops.backlog.queue import write_task_file
    write_task_file(task)

    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir(parents=True)
    (ssh_dir / "allowed_signers").write_text("signer@example.com ssh-ed25519 AAA...\n", encoding="utf-8")

    cfg = SpecOpsConfig(
        root_dir=tmp_path,
        security=SecuritySettings(
            compliance=ComplianceSettings(allowed_signers_file=".ssh/allowed_signers")
        ),
    )

    # 1. Lowercase "task-0099"
    ok, msg = sign_task_review("task-0099", "signer@example.com", cfg)
    assert ok is True
    assert "TASK-0099" in msg

    # Verify task file updated on disk
    from spec_ops.backlog.queue import BacklogQueue
    loaded = BacklogQueue(cfg.backlog_dir).list_all_tasks()
    assert loaded[0].signed_off_by == "signer@example.com"

    # 2. Task not found in backlog
    ok_missing, msg_missing = sign_task_review("TASK-9999", "signer@example.com", cfg)
    assert ok_missing is False
    assert "Task TASK-9999 not found in backlog." in msg_missing

    # 3. Numeric ID not found
    ok_num, msg_num = sign_task_review("8888", "signer@example.com", cfg)
    assert ok_num is False
    assert "Task 8888 not found in backlog." in msg_num


def test_verify_worker_integration_gates_compliance(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    (repo / "base.txt").write_text("base", encoding="utf-8")
    subprocess.run(["git", "add", "base.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "main base"], cwd=repo, check=True)

    # Clean branch without new commits
    subprocess.run(["git", "checkout", "-b", "feat/clean"], cwd=repo, check=True)

    task_unclaimed = Task(id="0002", title="Task 2", claimed_by="", signed_off_by="")
    cfg_dc = SpecOpsConfig(
        root_dir=repo,
        security=SecuritySettings(compliance=ComplianceSettings(dual_custody=True)),
    )
    # Fails dual custody because config enables it
    ok, msg = verify_worker_integration_gates(repo, "feat/clean", task_unclaimed, cfg_dc)
    assert ok is False
    assert "Dual-Custody Gate:" in msg
