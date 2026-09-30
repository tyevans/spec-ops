"""Generative property and unit tests for git commit verification and dual-custody gate."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, strategies as st

from spec_ops.backlog.queue import BacklogQueue, write_task_file
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


# ==============================================================================
# Hypothesis Generative Property Tests
# ==============================================================================


valid_tokens = st.from_regex(r"^[A-Za-z][A-Za-z0-9_-]{1,20}$", fullmatch=True)
clean_text = st.text(
    alphabet=st.characters(blacklist_categories=("Cs", "Cc"), blacklist_characters=("\r", "\n", "\0", ":")),
    min_size=1,
    max_size=50,
).map(str.strip).filter(bool)


@given(
    body=st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc"), blacklist_characters=("\r", "\0")), max_size=100),
    token=valid_tokens,
    val=clean_text,
)
def test_property_git_trailer_roundtrip(body: str, token: str, val: str):
    """Property: Injecting a trailer into any commit message can be parsed back with the exact value."""
    # Ensure body does not end with a trailer-like token line to avoid ambiguity
    safe_body = f"{body}\nSome body text" if body else "Some commit subject"
    trailers = {token: val}
    formatted = format_commit_message(safe_body, trailers)
    parsed = parse_git_trailers(formatted)
    assert token in parsed
    assert parsed[token] == val.strip()


@given(
    leading_nl=st.integers(min_value=0, max_value=5),
    trailing_nl=st.integers(min_value=0, max_value=5),
    spaces_around_colon=st.integers(min_value=0, max_value=3),
    token=valid_tokens,
    val=clean_text,
)
def test_property_varying_whitespace_trailers(
    leading_nl: int,
    trailing_nl: int,
    spaces_around_colon: int,
    token: str,
    val: str,
):
    """Property: Trailer parsing is invariant to varying blank lines and whitespace around colons."""
    pad = " " * spaces_around_colon
    msg = (
        ("Subject line\n\n" if leading_nl else "")
        + ("\n" * leading_nl)
        + f"{token}:{pad}{val}"
        + ("\n" * trailing_nl)
    )
    parsed = parse_git_trailers(msg)
    assert token in parsed
    assert parsed[token] == val.strip()


@given(
    name=clean_text.filter(lambda s: "<" not in s and ">" not in s and ";" not in s and len(s) > 1),
    user=st.from_regex(r"^[a-zA-Z0-9_.+-]+$", fullmatch=True),
    domain=st.from_regex(r"^[a-zA-Z0-9-]+\.[a-zA-Z]{2,6}$", fullmatch=True),
)
def test_property_validate_key_id_rfc2822(name: str, user: str, domain: str):
    """Property: Any well-formed Name <user@domain> or user@domain identity validates to True."""
    email = f"{user}@{domain}"
    rfc_id = f"{name} <{email}>"
    assert validate_key_id(rfc_id) is True
    assert validate_key_id(email) is True
    assert extract_email(rfc_id) == email.lower()
    assert extract_email(email) == email.lower()


@given(invalid_str=st.text(max_size=20).filter(lambda s: "\n" in s or "\0" in s or ";" in s or len(s) < 3))
def test_property_validate_key_id_invalid(invalid_str: str):
    """Property: Inputs with newlines, null bytes, semicolons, or undersized strings fail validation."""
    assert validate_key_id(invalid_str) is False


# ==============================================================================
# Unit & Mutation Coverage Tests for signing.py
# ==============================================================================


def test_validate_key_id_edge_cases():
    assert validate_key_id(123) is False  # type: ignore
    assert validate_key_id("") is False
    assert validate_key_id("a" * 300) is False
    assert validate_key_id("Riley <riley@example.com>") is True
    assert validate_key_id("riley@example.com") is True
    assert validate_key_id("B5690EEEBB952194") is True
    assert validate_key_id("412361F52C443AD259FB9A2351A2D37209CA45A9") is True
    assert validate_key_id("ABCD 1234 EF56 7890 ABCD 1234 EF56 7890 SPEC OPS1") is False  # not hex only
    assert validate_key_id("ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAI...") is True
    assert validate_key_id("ssh-rsa AAAAB3NzaC1yc2E...") is True
    assert validate_key_id("SHA256:JUgx3xMZmNaoeHEqvuDvkRhKlANwlqyNzUgOu6+hIJU") is True
    assert validate_key_id("random-invalid-string") is False


def test_extract_email():
    assert extract_email("") is None
    assert extract_email("No Email Here") is None
    assert extract_email("Riley <RILEY@Example.Com>") == "riley@example.com"
    assert extract_email("sasha@secure.org") == "sasha@secure.org"


def test_parse_git_trailers_multiline_and_empty():
    assert parse_git_trailers("") == {}
    assert parse_git_trailers("   ") == {}

    msg = "Commit subject\n\nSpecOps-Task: TASK-0042\nSpecOps-Signed-By: Riley <riley@example.com>\n  Continuation line\n"
    trailers = parse_git_trailers(msg)
    assert trailers["SpecOps-Task"] == "TASK-0042"
    assert "Continuation line" in trailers["SpecOps-Signed-By"]


def test_format_commit_message_empty_body():
    formatted = format_commit_message("", {"SpecOps-Task": "TASK-0001"})
    assert formatted == "SpecOps-Task: TASK-0001\n"

    formatted_empty = format_commit_message("", {})
    assert formatted_empty == ""


def test_load_authorized_signers_and_verify(tmp_path: Path):
    ssh_dir = tmp_path / ".ssh"
    ssh_dir.mkdir()
    allowed_file = ssh_dir / "allowed_signers"
    allowed_file.write_text(
        "# Comment line\nriley@example.com,mordan@example.com ssh-ed25519 AAAAC3...\n\n",
        encoding="utf-8",
    )

    config = SpecOpsConfig(
        root_dir=tmp_path,
        security=SecuritySettings(
            compliance=ComplianceSettings(
                authorized_signers=["Morgan <morgan@example.com>"],
                allowed_signers_file=".ssh/allowed_signers",
            )
        ),
    )

    signers = load_authorized_signers(config=config, repo_dir=tmp_path)
    assert "riley@example.com" in signers
    assert "morgan@example.com" in signers

    # Verify authorized
    ok, msg = verify_reviewer_identity("Riley <riley@example.com>", config=config, repo_dir=tmp_path)
    assert ok is True

    # Verify unauthorized
    ok, msg = verify_reviewer_identity("Eve <eve@attacker.com>", config=config, repo_dir=tmp_path)
    assert ok is False
    assert "not in authorized signers keyring" in msg

    # Verify invalid format
    ok, msg = verify_reviewer_identity("bad;identity", config=config, repo_dir=tmp_path)
    assert ok is False
    assert "Invalid identity format" in msg


def test_verify_branch_commit_signatures_simulation(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "commit.gpgsign", "false"], cwd=repo, check=True)

    # Empty repo / no commits
    ok, sha, msg = verify_branch_commit_signatures(repo, base_branch="main", target_branch="non-existent")
    assert ok is True

    # Add commit on main
    (repo / "file.txt").write_text("hello", encoding="utf-8")
    subprocess.run(["git", "add", "file.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=repo, check=True)

    # Checkout branch and add unsigned commit
    subprocess.run(["git", "checkout", "-b", "feature"], cwd=repo, check=True)
    (repo / "file2.txt").write_text("world", encoding="utf-8")
    subprocess.run(["git", "add", "file2.txt"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "feature commit"], cwd=repo, check=True)

    ok, unsigned_sha, msg = verify_branch_commit_signatures(repo, base_branch="main", target_branch="feature")
    assert ok is False
    assert unsigned_sha is not None
    assert f"Compliance Violation: Commit {unsigned_sha} lacks valid cryptographic signature (GPG/SSH)" == msg


# ==============================================================================
# Unit & Mutation Coverage Tests for dual_custody.py
# ==============================================================================


def test_is_autonomous_task():
    t_agent = Task(id="0001", title="T1", claimed_by="worker-1")
    assert is_autonomous_task(t_agent) is True

    t_body = Task(id="0002", title="T2", body="Provenance: spec-ops autonomous worker")
    assert is_autonomous_task(t_body) is True

    t_human = Task(id="0003", title="T3", claimed_by="")
    assert is_autonomous_task(t_human) is False

    cfg_dc = SpecOpsConfig(
        security=SecuritySettings(compliance=ComplianceSettings(dual_custody=True))
    )
    assert is_autonomous_task(t_human, config=cfg_dc) is True

    cfg_sig = SpecOpsConfig(
        security=SecuritySettings(compliance=ComplianceSettings(require_signed_commits=True))
    )
    assert is_autonomous_task(t_human, config=cfg_sig) is True


def test_evaluate_dual_custody_gate():
    t_agent = Task(id="0001", title="T1", claimed_by="worker-1")
    ok, msg = evaluate_dual_custody_gate(t_agent)
    assert ok is False
    assert "Dual-Custody Gate: Autonomous agent task requires verified human review sign-off" in msg
    assert "spec-ops review sign TASK-0001 --identity <key-id>" in msg

    t_agent.signed_off_by = "Riley <riley@example.com>"
    ok, msg = evaluate_dual_custody_gate(t_agent)
    assert ok is True
    assert msg == "Dual-custody verification passed."

    t_human = Task(id="0002", title="T2")
    ok, msg = evaluate_dual_custody_gate(t_human)
    assert ok is True


def test_record_sign_off(tmp_path: Path):
    t_file = tmp_path / "0001-task.md"
    task = Task(id="0001", title="Task 1", status="Refined", file_path=t_file)
    write_task_file(task)

    record_sign_off(task, "Riley <riley@example.com>", timestamp="2026-09-29T12:00:00Z")
    assert task.signed_off_by == "Riley <riley@example.com>"
    assert task.signed_off_at == "2026-09-29T12:00:00Z"

    content = t_file.read_text(encoding="utf-8")
    assert "signed_off_by: Riley <riley@example.com>" in content
    assert "signed_off_at: '2026-09-29T12:00:00Z'" in content or "signed_off_at: 2026-09-29T12:00:00Z" in content


def test_sign_task_review(tmp_path: Path):
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

    # Success
    ok, msg = sign_task_review("TASK-0042", "Riley <riley@example.com>", config)
    assert ok is True
    assert "review successfully signed" in msg

    # Task not found
    ok, msg = sign_task_review("TASK-9999", "Riley <riley@example.com>", config)
    assert ok is False
    assert "not found in backlog" in msg

    # Reviewer unauthorized
    ok, msg = sign_task_review("TASK-0042", "Eve <eve@attacker.com>", config)
    assert ok is False
    assert "not in authorized signers keyring" in msg
