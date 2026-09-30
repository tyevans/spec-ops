"""Comprehensive blackbox unit tests for Merkle compliance manifest generator and verifier."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from spec_ops.core.git_metadata import CommitInfo
from spec_ops.security.audit.exporter import (
    _extract_story_scenarios,
    _resolve_task_commit_sha,
    _resolve_task_signoff,
    export_compliance_manifest,
    extract_repo_compliance_deliverables,
)
from spec_ops.security.audit.merkle import (
    ComplianceDeliverable,
    ComplianceManifest,
    HumanSignoff,
    MerkleTree,
    compile_compliance_manifest,
    hash_leaf,
)
from spec_ops.security.audit.verifier import (
    VerificationResult,
    verify_audit_trail,
    verify_compliance_manifest,
)


def test_extract_story_scenarios_nonexistent_dir(tmp_path: Path):
    """Verifies scenario extraction when accepted stories directory does not exist."""
    res = _extract_story_scenarios(tmp_path, ["US-0056"])
    assert res == []


def test_extract_story_scenarios_formatting_and_deduplication(tmp_path: Path):
    """Verifies scenario titles are normalized with 'Scenario:' and duplicates removed."""
    stories_dir = tmp_path / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True)

    story_md = """---
id: '0056'
title: Audit Trail
---
# US-0056
Scenario: Alpha scenario
Scenario: Beta scenario
"""
    (stories_dir / "us-0056-audit-trail.md").write_text(story_md, encoding="utf-8")

    scenarios = _extract_story_scenarios(tmp_path, ["US-0056"])
    assert scenarios == ["Scenario: Alpha scenario", "Scenario: Beta scenario"]


def test_resolve_task_commit_sha_sources(tmp_path: Path):
    """Verifies commit SHA resolution priority: frontmatter > git history > deterministic fallback."""
    # Frontmatter takes highest priority
    meta_explicit = {"commit_sha": "a" * 40}
    assert _resolve_task_commit_sha(tmp_path, "TASK-0010", meta_explicit) == "a" * 40

    # Fallback deterministic commit SHA
    meta_empty: dict = {}
    fallback_sha = _resolve_task_commit_sha(tmp_path, "TASK-0010", meta_empty)
    assert len(fallback_sha) == 40
    assert fallback_sha == hashlib.sha256(b"commit:TASK-0010").hexdigest()[:40]


def test_resolve_task_signoff_parsing(tmp_path: Path):
    """Verifies parsing of human signoff from dictionary, name/email string, or default."""
    # From structured dict
    meta_dict = {
        "human_signoff": {
            "reviewer": "Alex",
            "email": "alex@example.com",
            "signature": "sig:alex",
            "timestamp": "2026-09-29T10:00:00Z",
            "decision": "APPROVED",
            "role": "Lead Architect",
        }
    }
    s1 = _resolve_task_signoff("TASK-0001", meta_dict, "", "")
    assert s1.reviewer == "Alex"
    assert s1.email == "alex@example.com"
    assert s1.signature == "sig:alex"
    assert s1.role == "Lead Architect"

    # From string with email
    s2 = _resolve_task_signoff("TASK-0001", {}, "Taylor <taylor@specops.dev>", "2026-09-29T12:00:00Z")
    assert s2.reviewer == "Taylor"
    assert s2.email == "taylor@specops.dev"
    assert s2.timestamp == "2026-09-29T12:00:00Z"

    # From string without email
    s3 = _resolve_task_signoff("TASK-0001", {}, "Morgan", "")
    assert s3.reviewer == "Morgan"
    assert s3.email == "morgan@specops.dev"

    # Default fallback
    s4 = _resolve_task_signoff("TASK-0001", {}, "", "")
    assert s4.reviewer == "Sasha"
    assert s4.email == "sasha@specops.dev"


def test_extract_repo_deliverables_empty_or_missing(tmp_path: Path):
    """Verifies extracting deliverables from non-existent or empty complete/ directory."""
    assert extract_repo_compliance_deliverables(tmp_path) == []

    complete_dir = tmp_path / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True)
    assert extract_repo_compliance_deliverables(tmp_path) == []


def test_export_compliance_manifest_creates_files(tmp_path: Path):
    """Verifies export_compliance_manifest generates JSON manifest and MERKLE_ROOT."""
    complete_dir = tmp_path / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True)

    task_file = complete_dir / "0001-setup.md"
    task_file.write_text(
        "---\nid: '0001'\ntitle: Setup\nstatus: Complete\n---\n# TASK-0001\nBody",
        encoding="utf-8",
    )

    out_dir = tmp_path / "dist" / "compliance"
    manifest_f, root_f, manifest = export_compliance_manifest(
        repo_dir=tmp_path,
        standard="iso27001",
        output_dir=out_dir,
    )

    assert manifest_f.is_file()
    assert root_f.is_file()
    assert manifest.standard == "iso27001"
    assert manifest.tree_size == 1

    data = json.loads(manifest_f.read_text(encoding="utf-8"))
    assert data["standard"] == "iso27001"
    assert data["root_hash"] == manifest.root_hash
    assert root_f.read_text(encoding="utf-8").strip() == manifest.root_hash


def test_verify_compliance_manifest_input_variations():
    """Verifies verify_compliance_manifest accepts ComplianceManifest object, dict, or JSON."""
    signoff = HumanSignoff("Sasha", "sasha@specops.dev", "sig:1", "2026-09-29T18:00:00Z")
    deliv = ComplianceDeliverable(
        task_id="TASK-0001",
        prd_id="PRD-0001",
        story_ids=["US-0001"],
        commit_sha="0" * 40,
        prompt_sha256="1" * 64,
        test_results_digest="2" * 64,
        human_signoff=signoff,
    )
    manifest = compile_compliance_manifest([deliv], standard="soc2")

    # From object
    ok1, err1 = verify_compliance_manifest(manifest)
    assert ok1 is True
    assert err1 == []

    # From dict
    ok2, err2 = verify_compliance_manifest(manifest.to_dict())
    assert ok2 is True
    assert err2 == []

    # From JSON string
    ok3, err3 = verify_compliance_manifest(manifest.to_json())
    assert ok3 is True
    assert err3 == []


def test_verify_audit_trail_nonexistent_or_invalid_json(tmp_path: Path):
    """Verifies audit trail verification fails cleanly on missing or malformed manifest file."""
    # Missing file
    res1 = verify_audit_trail(tmp_path / "missing.json", repo_dir=tmp_path)
    assert res1.ok is False
    assert res1.corrupted_entity_id == "MANIFEST_FILE"

    # Malformed JSON
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("NOT_VALID_JSON{{{", encoding="utf-8")
    res2 = verify_audit_trail(bad_json, repo_dir=tmp_path)
    assert res2.ok is False
    assert res2.corrupted_entity_id == "MANIFEST_JSON"


def test_verify_audit_trail_companion_root_mismatch(tmp_path: Path):
    """Verifies companion MERKLE_ROOT file tampering is detected."""
    complete_dir = tmp_path / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True)
    task_file = complete_dir / "0001-setup.md"
    task_file.write_text("---\nid: '0001'\ntitle: Setup\nstatus: Complete\n---\n# TASK-0001\nBody", encoding="utf-8")

    out_dir = tmp_path / "dist" / "compliance"
    manifest_f, root_f, manifest = export_compliance_manifest(tmp_path, "soc2", out_dir)

    # Tamper with companion root
    root_f.write_text("ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff\n", encoding="utf-8")

    res = verify_audit_trail(manifest_f, repo_dir=tmp_path)
    assert res.ok is False
    assert res.corrupted_entity_id == "MERKLE_ROOT"


def test_verify_audit_trail_missing_complete_task_file(tmp_path: Path):
    """Verifies detection of missing completed task file (broken traceability)."""
    complete_dir = tmp_path / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True)
    task_file = complete_dir / "0001-setup.md"
    task_file.write_text("---\nid: '0001'\ntitle: Setup\nstatus: Complete\n---\n# TASK-0001\nBody", encoding="utf-8")

    out_dir = tmp_path / "dist" / "compliance"
    manifest_f, root_f, manifest = export_compliance_manifest(tmp_path, "soc2", out_dir)

    # Delete task file out-of-band
    task_file.unlink()

    res = verify_audit_trail(manifest_f, repo_dir=tmp_path)
    assert res.ok is False
    assert res.corrupted_entity_id == "TASK-0001"
    assert res.computed_hash == "FILE_NOT_FOUND"


def test_cli_audit_export_and_verify_end_to_end(tmp_path: Path):
    """Verifies CLI execution of spec-ops audit export and verify via main module."""
    complete_dir = tmp_path / "docs" / "project" / "backlog" / "complete"
    complete_dir.mkdir(parents=True)
    task_file = complete_dir / "0010-feature.md"
    task_file.write_text(
        "---\n"
        "id: '0010'\n"
        "title: Feature\n"
        "status: Complete\n"
        "commit_sha: 'aaaaabbbbbcccccdddddeeeeefffff0000011111'\n"
        "signed_off_by: 'Sasha <sasha@specops.dev>'\n"
        "signoff_signature: 'sig:0010'\n"
        "---\n"
        "# TASK-0010\nContent",
        encoding="utf-8",
    )
    (tmp_path / "specops.toml").write_text('[project]\nname = "EndToEndApp"\n', encoding="utf-8")

    from spec_ops.cli.main import main

    # Run export
    export_args = ["spec-ops", "audit", "export", "--standard", "soc2", "--output", str(tmp_path / "dist" / "compliance")]
    with patch.object(sys, "argv", export_args), patch("spec_ops.cli.main.load_config") as mock_conf:
        from spec_ops.config.models import ProjectSettings, SpecOpsConfig
        mock_conf.return_value = SpecOpsConfig(
            project=ProjectSettings(name="EndToEndApp"),
            root_dir=tmp_path,
        )
        ret_export = main()
        assert ret_export == 0

    manifest_path = tmp_path / "dist" / "compliance" / "soc2-audit-manifest.json"
    assert manifest_path.is_file()

    # Run verify (success)
    verify_args = ["spec-ops", "audit", "verify", "--manifest", str(manifest_path), "--repo", str(tmp_path)]
    with patch.object(sys, "argv", verify_args), patch("spec_ops.cli.main.load_config") as mock_conf:
        mock_conf.return_value = SpecOpsConfig(
            project=ProjectSettings(name="EndToEndApp"),
            root_dir=tmp_path,
        )
        ret_verify = main()
        assert ret_verify == 0

    # Tamper with file
    task_file.write_text(task_file.read_text(encoding="utf-8") + "\nTAMPERED", encoding="utf-8")

    # Run verify (failure)
    with patch.object(sys, "argv", verify_args), patch("spec_ops.cli.main.load_config") as mock_conf:
        mock_conf.return_value = SpecOpsConfig(
            project=ProjectSettings(name="EndToEndApp"),
            root_dir=tmp_path,
        )
        ret_verify_tampered = main()
        assert ret_verify_tampered == 1
