"""Unit and mutation kill tests for spec_ops.prd.uat_gatekeeper."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from spec_ops.config.loader import load_config
from spec_ops.prd.uat import record_uat_signoff
from spec_ops.prd.uat_gatekeeper import (
    canonical_prd_id,
    compute_uat_token_signature,
    evaluate_uat_gate,
    export_uat_token,
    find_prd_file,
    handle_prd_gate,
    load_uat_token,
)
from spec_ops.scaffold.init import init_project


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "test_repo"
    repo.mkdir(parents=True, exist_ok=True)
    init_project(name="GateTestApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@specops.test"], cwd=repo, check=True, capture_output=True)

    # Accepted PRD
    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    prd_file = prd_dir / "prd-0004-notifications.md"
    prd_file.write_text(
        """---
id: PRD-0004
title: Real-time Notifications
status: Accepted
---

# PRD-0004: Real-time Notifications

## Checkable Outcomes
1. User receives instant toast notification on status change
2. Failed notifications are queued for retry
""",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: setup prd-0004"], cwd=repo, check=True, capture_output=True)
    return repo


def test_canonical_prd_id() -> None:
    assert canonical_prd_id("PRD-0004") == "PRD-0004"
    assert canonical_prd_id("prd-4") == "PRD-0004"
    assert canonical_prd_id(4) == "PRD-0004"
    assert canonical_prd_id("custom-prd") == "CUSTOM-PRD"


def test_compute_uat_token_signature() -> None:
    sig = compute_uat_token_signature("PRD-0004", "a" * 64, "Signer <s@specops.local>", [])
    assert isinstance(sig, str)
    assert len(sig) == 64
    sig2 = compute_uat_token_signature("4", "a" * 64, "Signer <s@specops.local>", [])
    assert sig == sig2


def test_find_prd_file(test_repo: Path) -> None:
    f, clean_id = find_prd_file(test_repo, "PRD-0004")
    assert f is not None
    assert f.name == "prd-0004-notifications.md"
    assert clean_id == "PRD-0004"

    f2, clean_id2 = find_prd_file(test_repo, "PRD-9999")
    assert f2 is None
    assert clean_id2 == "PRD-9999"


def test_find_prd_file_in_shipped_or_shaped(tmp_path: Path) -> None:
    repo = tmp_path / "repo2"
    repo.mkdir(parents=True, exist_ok=True)
    shipped_dir = repo / "docs" / "project" / "product" / "shipped"
    shipped_dir.mkdir(parents=True, exist_ok=True)
    f = shipped_dir / "prd-0007-archive.md"
    f.write_text("# PRD-0007 Archive", encoding="utf-8")

    res, cid = find_prd_file(repo, "PRD-0007")
    assert res is not None
    assert res.name == "prd-0007-archive.md"
    assert cid == "PRD-0007"


def test_find_prd_file_by_header(tmp_path: Path) -> None:
    repo = tmp_path / "repo3"
    repo.mkdir(parents=True, exist_ok=True)
    pdir = repo / "docs" / "project" / "product"
    pdir.mkdir(parents=True, exist_ok=True)
    f = pdir / "unusual-name.md"
    f.write_text("---\nid: PRD-0012\n---\n# Some doc", encoding="utf-8")

    res, cid = find_prd_file(repo, "PRD-0012")
    assert res is not None
    assert res.name == "unusual-name.md"
    assert cid == "PRD-0012"


def test_export_uat_token_and_load(test_repo: Path) -> None:
    record_uat_signoff(test_repo, "PRD-0004", "1", "Taylor PM <taylor@specops.local>", "Approved")
    record_uat_signoff(test_repo, "PRD-0004", "2", "Taylor PM <taylor@specops.local>", "Approved")

    token = export_uat_token(test_repo, "PRD-0004", signer="Auditor <auditor@specops.local>")
    assert token["prd_id"] == "PRD-0004"
    assert token["signer"] == "Auditor <auditor@specops.local>"
    assert len(token["token_signature"]) == 64
    assert Path(token["path"]).is_file()

    loaded_token, path = load_uat_token(test_repo, "PRD-0004")
    assert loaded_token is not None
    assert path is not None
    assert loaded_token["token_signature"] == token["token_signature"]


def test_export_uat_token_missing_prd(test_repo: Path) -> None:
    with pytest.raises(FileNotFoundError, match="not found"):
        export_uat_token(test_repo, "PRD-8888")


def test_evaluate_uat_gate_missing_prd(test_repo: Path) -> None:
    dec = evaluate_uat_gate(test_repo, "PRD-9999")
    assert dec.decision == "BLOCKED"
    assert dec.readiness_percentage == 0.0
    assert "not found" in dec.blocking_reasons[0]


def test_evaluate_uat_gate_zero_outcomes(tmp_path: Path) -> None:
    repo = tmp_path / "zero_repo"
    repo.mkdir(parents=True, exist_ok=True)
    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0010-empty.md").write_text("# PRD-0010 Empty", encoding="utf-8")

    dec_non_strict = evaluate_uat_gate(repo, "PRD-0010", strict=False)
    assert dec_non_strict.decision == "PASS"

    dec_strict = evaluate_uat_gate(repo, "PRD-0010", strict=True)
    assert dec_strict.decision == "BLOCKED"
    assert "zero checkable outcomes" in dec_strict.blocking_reasons[0]


def test_evaluate_uat_gate_allowed_signers_enforcement(test_repo: Path) -> None:
    allowed_file = test_repo / ".allowed_signers"
    allowed_file.write_text("authorized@specops.local ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA\n", encoding="utf-8")

    record_uat_signoff(test_repo, "PRD-0004", "1", "Impostor <impostor@specops.local>", "Approved")
    record_uat_signoff(test_repo, "PRD-0004", "2", "Impostor <impostor@specops.local>", "Approved")

    dec = evaluate_uat_gate(test_repo, "PRD-0004", strict=False)
    assert dec.decision == "BLOCKED"
    assert any("not in authorized keyring" in b for b in dec.blocking_reasons)


def test_evaluate_uat_gate_invalid_rfc2822_reviewer(test_repo: Path) -> None:
    tdir = test_repo / ".specops" / "uat_receipts"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "PRD-0004-uat-token.json").write_text(
        json.dumps(
            {
                "$schema": "spec-ops/uat-token-v1",
                "version": "1.0",
                "prd_id": "PRD-0004",
                "signer": "Taylor PM <taylor@specops.local>",
                "tree_digest": "0" * 64,
                "outcomes": [
                    {"outcome_id": "1", "status": "Approved", "reviewer": "InvalidNoEmail"},
                    {"outcome_id": "2", "status": "Approved", "reviewer": "Taylor PM <taylor@specops.local>"},
                ],
                "token_signature": "",
            }
        ),
        encoding="utf-8",
    )
    dec = evaluate_uat_gate(test_repo, "PRD-0004", strict=False)
    assert dec.decision == "BLOCKED"
    assert any("invalid RFC 2822" in b for b in dec.blocking_reasons)


def test_evaluate_uat_gate_missing_reviewer(test_repo: Path) -> None:
    tdir = test_repo / ".specops" / "uat_receipts"
    tdir.mkdir(parents=True, exist_ok=True)
    (tdir / "PRD-0004-uat-token.json").write_text(
        json.dumps(
            {
                "$schema": "spec-ops/uat-token-v1",
                "version": "1.0",
                "prd_id": "PRD-0004",
                "signer": "Taylor PM <taylor@specops.local>",
                "tree_digest": "0" * 64,
                "outcomes": [
                    {"outcome_id": "1", "status": "Approved", "reviewer": ""},
                    {"outcome_id": "2", "status": "Approved", "reviewer": ""},
                ],
                "token_signature": "",
            }
        ),
        encoding="utf-8",
    )
    dec = evaluate_uat_gate(test_repo, "PRD-0004", strict=False)
    assert dec.decision == "BLOCKED"
    assert any("Missing reviewer identity" in b for b in dec.blocking_reasons)


def test_evaluate_uat_gate_corrupt_token_file(test_repo: Path) -> None:
    token_dir = test_repo / ".specops" / "uat_receipts"
    token_dir.mkdir(parents=True, exist_ok=True)
    (token_dir / "PRD-0004-uat-token.json").write_text("{corrupt json", encoding="utf-8")

    data, path = load_uat_token(test_repo, "PRD-0004")
    assert data is None


def test_evaluate_uat_gate_tampered_token_signature(test_repo: Path) -> None:
    record_uat_signoff(test_repo, "PRD-0004", "1", "Taylor PM <taylor@specops.local>", "Approved")
    record_uat_signoff(test_repo, "PRD-0004", "2", "Taylor PM <taylor@specops.local>", "Approved")

    token_dir = test_repo / ".specops" / "uat_receipts"
    token_dir.mkdir(parents=True, exist_ok=True)
    token_file = token_dir / "PRD-0004-uat-token.json"
    token_file.write_text(
        json.dumps(
            {
                "$schema": "spec-ops/uat-token-v1",
                "version": "1.0",
                "prd_id": "PRD-0004",
                "signer": "Taylor PM <taylor@specops.local>",
                "tree_digest": "0" * 64,
                "outcomes": [],
                "token_signature": "bad_signature_tampered",
            }
        ),
        encoding="utf-8",
    )

    dec = evaluate_uat_gate(test_repo, "PRD-0004", strict=True)
    assert any(not o.token_verified for o in dec.outcomes)


def test_evaluate_uat_gate_with_customer_uat_receipt(test_repo: Path) -> None:
    from spec_ops.prd.uat_cli import generate_customer_uat_receipt
    record_uat_signoff(test_repo, "PRD-0004", "1", "Taylor PM <taylor@specops.local>", "Approved")
    record_uat_signoff(test_repo, "PRD-0004", "2", "Taylor PM <taylor@specops.local>", "Approved")
    receipt = generate_customer_uat_receipt(test_repo, "PRD-0004", allow_uncommitted=True)
    assert receipt is not None

    dec = evaluate_uat_gate(test_repo, "PRD-0004", strict=False)
    assert dec.decision == "PASS"


def test_handle_prd_gate_cli(test_repo: Path, capsys: pytest.CaptureFixture[str]) -> None:
    cfg = load_config(test_repo)
    rc = handle_prd_gate(cfg, "PRD-0004", strict=False, json_output=False)
    assert rc == 1
    out = capsys.readouterr().out
    assert "Gate Decision: ❌ BLOCKED" in out

    rc_json = handle_prd_gate(cfg, "PRD-0004", strict=False, json_output=True)
    assert rc_json == 1
    out_json = capsys.readouterr().out
    data = json.loads(out_json)
    assert data["decision"] == "BLOCKED"

    rc_export = handle_prd_gate(cfg, "PRD-0004", strict=False, json_output=False, export=True)
    out_exp = capsys.readouterr().out
    assert "Exported customer UAT token" in out_exp

    record_uat_signoff(test_repo, "PRD-0004", "1", "Taylor PM <taylor@specops.local>", "Approved")
    record_uat_signoff(test_repo, "PRD-0004", "2", "Taylor PM <taylor@specops.local>", "Approved")
    rc_pass = handle_prd_gate(cfg, "PRD-0004", strict=False, json_output=False)
    assert rc_pass == 0
    out_pass = capsys.readouterr().out
    assert "Gate Decision: ✅ PASS" in out_pass


def test_handle_prd_gate_export_failure(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    empty_repo = tmp_path / "empty"
    empty_repo.mkdir()
    cfg = load_config(empty_repo)
    rc = handle_prd_gate(cfg, "PRD-8888", export=True)
    assert rc == 1
    out = capsys.readouterr().out
    assert "Failed to export customer UAT token" in out
