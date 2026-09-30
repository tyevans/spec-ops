"""Unit tests for security posture calculation, commit evaluation, and harvesting."""

from __future__ import annotations

import tempfile
from pathlib import Path
from typing import Any

import pytest

from spec_ops.config.loader import load_config
from spec_ops.scaffold.init import init_project
from spec_ops.visualizer.security_metrics import (
    aggregate_project_compliance,
    aggregate_vulnerability_counts,
    assess_task_compliance,
    calculate_human_signoff_rate,
    calculate_signed_commit_coverage,
    evaluate_lockfile_integrity,
    evaluate_secret_scan_status,
    evaluate_task_human_signoff,
    evaluate_task_signed_commits,
    format_vulnerability_indicator,
    harvest_security_posture,
)


def test_calculate_signed_commit_coverage_edge_cases() -> None:
    assert calculate_signed_commit_coverage(0, 0) == 100.0
    assert calculate_signed_commit_coverage(-5, 0) == 100.0
    assert calculate_signed_commit_coverage(-1, 10) == 0.0
    assert calculate_signed_commit_coverage(0, 10) == 0.0
    assert calculate_signed_commit_coverage(10, 10) == 100.0
    assert calculate_signed_commit_coverage(12, 10) == 100.0
    assert calculate_signed_commit_coverage(5, 10) == 50.0
    assert calculate_signed_commit_coverage(1, 3) == 33.3


def test_calculate_human_signoff_rate_edge_cases() -> None:
    assert calculate_human_signoff_rate(0, 0) == 100.0
    assert calculate_human_signoff_rate(-2, -5) == 100.0
    assert calculate_human_signoff_rate(0, 20) == 0.0
    assert calculate_human_signoff_rate(-3, 20) == 0.0
    assert calculate_human_signoff_rate(20, 20) == 100.0
    assert calculate_human_signoff_rate(25, 20) == 100.0
    assert calculate_human_signoff_rate(19, 20) == 95.0
    assert calculate_human_signoff_rate(49, 50) == 98.0


def test_evaluate_secret_scan_status_and_lockfile() -> None:
    assert evaluate_secret_scan_status(0) == "Pass"
    assert evaluate_secret_scan_status(1) == "Fail"
    assert evaluate_secret_scan_status(99) == "Fail"

    assert evaluate_lockfile_integrity(True) == "Synchronized"
    assert evaluate_lockfile_integrity(False) == "Modified"


def test_aggregate_vulnerability_counts_and_indicator() -> None:
    class DummyVuln:
        def __init__(self, sev: str):
            self.severity = sev

    cves = [
        {"severity": "low"},
        {"severity": "LOW"},
        {"severity": "medium"},
        {"severity": "mod"},
        DummyVuln("moderate"),
        {"severity": "high"},
        DummyVuln("critical"),
    ]
    counts = aggregate_vulnerability_counts(cves)
    assert counts["low"] == 2
    assert counts["med"] == 3
    assert counts["high"] == 2
    assert counts["total"] == 7

    assert format_vulnerability_indicator(counts) == "2 Low / 3 Med / 2 High"
    assert format_vulnerability_indicator({}) == "0 Low / 0 Med / 0 High"
    assert format_vulnerability_indicator({"low": 1}) == "1 Low / 0 Med / 0 High"
    assert format_vulnerability_indicator({"med": 4}) == "0 Low / 4 Med / 0 High"
    assert format_vulnerability_indicator({"high": 5}) == "0 Low / 0 Med / 5 High"


def test_evaluate_task_signed_commits_variations() -> None:
    assert evaluate_task_signed_commits({"has_signed_commits": True}) is True
    assert evaluate_task_signed_commits({"has_signed_commits": False}) is False

    assert evaluate_task_signed_commits({"commit_signature_status": "Signed"}) is True
    assert evaluate_task_signed_commits({"commit_signature_status": "G"}) is True
    assert evaluate_task_signed_commits({"commit_signature_status": "U"}) is True
    assert evaluate_task_signed_commits({"commit_signature_status": "valid"}) is True
    assert evaluate_task_signed_commits({"commit_signature_status": "TRUE"}) is True
    assert evaluate_task_signed_commits({"commit_signature_status": "Unsigned"}) is False
    assert evaluate_task_signed_commits({"commit_signature_status": "N"}) is False
    assert evaluate_task_signed_commits({"commit_signature_status": "INVALID"}) is False
    assert evaluate_task_signed_commits({"commit_signature_status": "FALSE"}) is False

    # Commits list variations
    assert evaluate_task_signed_commits({"commits": [{"is_signed": True}, {"signature_status": "G"}]}) is True
    assert evaluate_task_signed_commits({"commits": [{"signature_status": "SIGNED"}]}) is True
    assert evaluate_task_signed_commits({"commits": [{"signature_status": "U"}]}) is True
    assert evaluate_task_signed_commits({"commits": [{"is_signed": False}]}) is False
    assert evaluate_task_signed_commits({"commits": [{"signature_status": "N"}]}) is False
    assert evaluate_task_signed_commits({"commits": [{"signature_status": "UNSIGNED"}]}) is False
    assert evaluate_task_signed_commits({"commits": [{"signature_status": "INVALID"}]}) is False
    assert evaluate_task_signed_commits({"commits": [{"signature_status": "OTHER"}]}) is False
    assert evaluate_task_signed_commits({"commits": ["invalid-not-dict"]}) is False

    # Metadata flags
    assert evaluate_task_signed_commits({"commit_signed": True}) is True
    assert evaluate_task_signed_commits({"signed_commits": True}) is True
    assert evaluate_task_signed_commits({}) is False


def test_evaluate_task_human_signoff_variations() -> None:
    assert evaluate_task_human_signoff({"has_human_signoff": True}) is True
    assert evaluate_task_human_signoff({"has_human_signoff": False}) is False

    assert evaluate_task_human_signoff({"signed_off_by": "Sasha <sasha@specops.dev>"}) is True
    assert evaluate_task_human_signoff({"signed_off_by": "   "}) is False

    assert evaluate_task_human_signoff({"human_signoff": {"reviewer": "Sasha"}}) is True
    assert evaluate_task_human_signoff({"human_signoff": {"reviewer": ""}}) is False
    assert evaluate_task_human_signoff({"human_signoff": {}}) is False
    assert evaluate_task_human_signoff({"human_signoff": "Approved by Sasha"}) is True
    assert evaluate_task_human_signoff({"human_signoff": "  "}) is False

    assert evaluate_task_human_signoff({"signoff_signature": "ed25519:abcdef"}) is True
    assert evaluate_task_human_signoff({"signoff_signature": ""}) is False
    assert evaluate_task_human_signoff({"signoff_signature": "  "}) is False
    assert evaluate_task_human_signoff({}) is False


def test_assess_task_compliance_details() -> None:
    compliant_task = {
        "id": "TASK-0010",
        "title": "Clean Task",
        "status": "Complete",
        "target_bc": "security",
        "signed_off_by": "Sasha",
        "signed_off_at": "2026-09-29T18:00:00Z",
        "has_human_signoff": True,
        "has_signed_commits": True,
        "cve_count": 0,
    }
    res = assess_task_compliance(compliant_task)
    assert res["id"] == "TASK-0010"
    assert res["title"] == "Clean Task"
    assert res["status"] == "Complete"
    assert res["target_bc"] == "security"
    assert res["signed_off_by"] == "Sasha"
    assert res["signed_off_at"] == "2026-09-29T18:00:00Z"
    assert res["is_compliant"] is True
    assert res["status_label"] == "Compliant"
    assert len(res["missing_artifacts"]) == 0
    assert res["permalink"] == "#tab=security&entity=TASK-0010"

    # Canonical ID fallback
    res_canon = assess_task_compliance({"canonical_id": "TASK-0020"})
    assert res_canon["id"] == "TASK-0020"
    assert res_canon["status"] == "Proposed"
    assert res_canon["is_compliant"] is False
    assert res_canon["status_label"] == "Non-Compliant (Blocking)"

    # Empty task fallback
    res_empty = assess_task_compliance({})
    assert res_empty["id"] == "TASK-0000"

    # CVE list
    res_cves = assess_task_compliance({
        "id": "TASK-0099",
        "has_human_signoff": True,
        "has_signed_commits": True,
        "cves": [{"severity": "high"}, {"severity": "low"}],
    })
    assert res_cves["cve_count"] == 2
    assert res_cves["is_compliant"] is False
    assert "2 Open CVE(s)" in res_cves["missing_artifacts"]


def test_aggregate_project_compliance_details() -> None:
    p_agg = aggregate_project_compliance(
        tasks=[
            {"id": "TASK-0001", "has_human_signoff": True, "has_signed_commits": True, "cve_count": 0},
            {"id": "TASK-0002", "has_human_signoff": False, "has_signed_commits": True, "cve_count": 0},
            {"id": "TASK-0003", "has_human_signoff": True, "has_signed_commits": False, "cve_count": 1},
        ],
        secret_clean=False,
        lockfile_clean=False,
        cves=[{"severity": "high"}],
    )
    assert p_agg["total_tasks"] == 3
    assert p_agg["compliant_count"] == 1
    assert p_agg["non_compliant_count"] == 2
    assert p_agg["signed_commit_coverage"] == 66.7
    assert p_agg["signed_commit_coverage_display"] == "66.7%"
    assert p_agg["human_signoff_rate"] == 66.7
    assert p_agg["human_signoff_rate_display"] == "66.7%"
    assert p_agg["secret_scan_status"] == "Fail"
    assert p_agg["lockfile_integrity"] == "Modified"
    assert p_agg["vulnerability_counts"]["high"] == 1
    assert p_agg["vulnerability_indicator"] == "0 Low / 0 Med / 1 High"


def test_harvest_security_posture_on_scaffolded_project(tmp_path: Path) -> None:
    init_project(tmp_path, name="SecurityTestProject")
    config = load_config(root_dir=tmp_path)

    tasks = [
        {"id": "TASK-0001", "has_human_signoff": True, "has_signed_commits": True, "cve_count": 0},
        {"id": "TASK-0002", "has_human_signoff": False, "has_signed_commits": True, "cve_count": 0},
    ]

    posture = harvest_security_posture(config, tasks=tasks)
    assert posture["total_tasks"] == 2
    assert posture["compliant_count"] == 1
    assert posture["non_compliant_count"] == 1
    assert posture["signed_commit_coverage"] == 100.0
    assert posture["human_signoff_rate"] == 50.0
    assert posture["secret_scan_status"] in ("Pass", "Fail")
    assert posture["lockfile_integrity"] in ("Synchronized", "Modified")

    empty_posture = harvest_security_posture(config, tasks=None)
    assert empty_posture["total_tasks"] == 0
