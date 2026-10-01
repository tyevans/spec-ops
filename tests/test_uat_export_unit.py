"""Unit tests for standalone Customer UAT Matrix HTML export and verification."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from spec_ops.config.loader import load_config
from spec_ops.prd.uat import record_uat_signoff
from spec_ops.prd.uat_export import (
    compute_ledger_digest,
    export_uat_matrix_html,
    render_uat_matrix_html,
    verify_exported_matrix_proof,
)
from spec_ops.scaffold.init import init_project


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(repo, name="TestUATExport")

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Tester"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "tester@specops.dev"], cwd=repo, check=True, capture_output=True)

    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0003-test.md").write_text(
        """---
id: '0003'
title: Product Discovery Studio
status: Accepted
target_persona: Taylor (The Product Manager)
component: prd
---

# PRD-0003 — Product Discovery Studio

## Checkable Outcomes

1. System provides interactive visual studio for editing PRDs.
2. System exports standalone Customer UAT acceptance matrix.
""",
        encoding="utf-8",
    )

    record_uat_signoff(
        repo_root=repo,
        prd_id="PRD-0003",
        outcome_id="1",
        reviewer="Taylor <taylor@specops.local>",
        status="Approved",
        notes="All scenarios verified",
    )
    record_uat_signoff(
        repo_root=repo,
        prd_id="PRD-0003",
        outcome_id="2",
        reviewer="Taylor <taylor@specops.local>",
        status="Approved",
        notes="Standalone HTML verified",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: setup test repo"], cwd=repo, check=True, capture_output=True)
    return repo


def test_render_uat_matrix_html(test_repo: Path):
    html_doc, meta = render_uat_matrix_html(test_repo, "PRD-0003")

    assert "<!DOCTYPE html>" in html_doc
    assert "Customer UAT Acceptance Matrix - PRD-0003" in html_doc
    assert meta["prd"]["id"] == "PRD-0003"
    assert meta["readiness"] == 100.0
    assert len(meta["signature"]) == 64
    assert len(meta["tree_digest"]) == 64
    assert len(meta["ledger_digest"]) == 64

    # Meta tags present
    assert '<meta name="spec-ops:prd-id" content="PRD-0003">' in html_doc
    assert f'<meta name="spec-ops:receipt-signature" content="{meta["signature"]}">' in html_doc
    assert f'<meta name="spec-ops:tree-digest" content="{meta["tree_digest"]}">' in html_doc
    assert f'<meta name="spec-ops:ledger-digest" content="{meta["ledger_digest"]}">' in html_doc

    # Checkable outcomes rendered
    assert "System provides interactive visual studio for editing PRDs." in html_doc
    assert "System exports standalone Customer UAT acceptance matrix." in html_doc


def test_export_uat_matrix_html_default_and_custom_path(test_repo: Path):
    # Default path
    out_file, html_doc, meta = export_uat_matrix_html(test_repo, "PRD-0003")
    assert out_file == test_repo / "dist" / "uat" / "PRD-0003-uat-matrix.html"
    assert out_file.is_file()
    assert out_file.read_text(encoding="utf-8") == html_doc

    # Custom path
    custom_dest = test_repo / "reports" / "custom-acceptance.html"
    custom_file, _, _ = export_uat_matrix_html(test_repo, "PRD-0003", output_path=custom_dest)
    assert custom_file == custom_dest
    assert custom_dest.is_file()


def test_export_uat_matrix_unsupported_format(test_repo: Path):
    with pytest.raises(ValueError, match="Unsupported format 'pdf'"):
        export_uat_matrix_html(test_repo, "PRD-0003", fmt="pdf")


def test_verify_exported_matrix_proof_valid(test_repo: Path):
    out_file, _, _ = export_uat_matrix_html(test_repo, "PRD-0003")
    valid, issues = verify_exported_matrix_proof(out_file, test_repo)
    assert valid is True
    assert issues == []


def test_verify_exported_matrix_proof_tampered_html(test_repo: Path):
    out_file, html_doc, meta = export_uat_matrix_html(test_repo, "PRD-0003")

    # Tamper with the receipt signature in the HTML
    tampered_html = html_doc.replace(meta["signature"], "a" * 64)
    valid, issues = verify_exported_matrix_proof(tampered_html, test_repo)
    assert valid is False
    assert any("Tampering detected" in err for err in issues)


def test_verify_exported_matrix_proof_tampered_ledger(test_repo: Path):
    out_file, _, _ = export_uat_matrix_html(test_repo, "PRD-0003")

    # Tamper with the signoff ledger file on disk
    ledger_path = test_repo / "docs" / "project" / "product" / "uat-signoff.json"
    data = json.loads(ledger_path.read_text(encoding="utf-8"))
    data["signoffs"]["PRD-0003:1"]["status"] = "Rejected"
    ledger_path.write_text(json.dumps(data), encoding="utf-8")

    valid, issues = verify_exported_matrix_proof(out_file, test_repo)
    assert valid is False
    assert any("Tampering detected" in err for err in issues)


def test_verify_exported_matrix_proof_missing_meta():
    broken_html = "<html><body><h1>No meta tags</h1></body></html>"
    valid, issues = verify_exported_matrix_proof(broken_html, Path.cwd())
    assert valid is False
    assert any("Missing required meta tag" in err for err in issues)


def test_html_escaping_xss_protection(tmp_path: Path):
    repo = tmp_path / "xss_repo"
    repo.mkdir()
    init_project(repo, name="XSSApp")
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Taylor"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "taylor@specops.dev"], cwd=repo, check=True, capture_output=True)

    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0001-xss.md").write_text(
        """---
id: '0001'
title: XSS <script>alert("pwnd")</script> Test
status: Accepted
target_persona: Taylor (The Product Manager)
component: prd
---

# PRD-0001

## Checkable Outcomes

1. Outcome with <script>evil()</script> injection and "quotes".
""",
        encoding="utf-8",
    )

    record_uat_signoff(
        repo_root=repo,
        prd_id="PRD-0001",
        outcome_id="1",
        reviewer='Hacker <hacker@evil.com">',
        status="Approved",
        notes='Review notes with <img src=x onerror=alert(1)> and "bold" characters',
    )
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: setup xss repo"], cwd=repo, check=True, capture_output=True)

    html_doc, _ = render_uat_matrix_html(repo, "PRD-0001")

    # Script and img tags must be strictly escaped
    assert "<script>evil()</script>" not in html_doc
    assert "&lt;script&gt;evil()&lt;/script&gt;" in html_doc
    assert "<img src=x onerror=alert(1)>" not in html_doc
    assert "&lt;img src=x onerror=alert(1)&gt;" in html_doc


def test_zero_external_network_calls(test_repo: Path):
    html_doc, _ = render_uat_matrix_html(test_repo, "PRD-0003")
    assert "http://" not in html_doc
    assert "https://" not in html_doc
    assert "cdn" not in html_doc.lower()


def test_cli_dispatch_export(test_repo: Path):
    cmd = [sys.executable, "-m", "spec_ops.cli.main", "prd", "uat", "export", "--prd", "PRD-0003", "--format", "html"]
    res = subprocess.run(cmd, cwd=test_repo, capture_output=True, text=True)
    assert res.returncode == 0
    assert "Exported Customer UAT Acceptance Matrix for PRD-0003" in res.stdout
    assert (test_repo / "dist" / "uat" / "PRD-0003-uat-matrix.html").is_file()
