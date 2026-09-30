"""Frontdoor unit and integration tests for living UAT receipts and release manifests."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from spec_ops.prd.manifest import (
    compute_git_tree_digest,
    compute_manifest_signature,
    generate_release_manifest,
    verify_release_manifest,
)
from spec_ops.prd.uat_receipt import (
    TestCorrelation,
    UATSignOffEntry,
    compute_delivery_readiness,
    extract_prd_outcomes,
    map_outcomes_to_tests,
    reconcile_signoffs,
    serialize_canonical_json,
    validate_uat_signoff_schema,
)


SAMPLE_PRD = """# PRD-0003: Living UAT Verification

## Checkable Outcomes

1. Launch web studio without terminal.
2. Lint checkable outcomes for falsifiability.
"""


def test_uat_signoff_schema_validation_valid():
    entry = UATSignOffEntry(
        outcome_id="1",
        prd_id="PRD-0003",
        status="Approved",
        reviewer="Taylor <taylor@example.com>",
        timestamp="2026-09-29T18:00:00Z",
        notes="All scenarios verified",
        test_correlation=TestCorrelation(
            scenario="Scenario: Test 1",
            story_id="US-0046",
            passed=True,
            test_run_id="run-1",
        ),
        history=[{"timestamp": "2026-09-29T17:00:00Z", "reviewer": "Taylor <taylor@example.com>", "status": "Pending"}],
    )
    payload = {
        "$schema": "spec-ops/uat-signoff-v1",
        "version": "1.0",
        "signoffs": {"PRD-0003:1": entry.to_dict()},
    }
    valid, violations = validate_uat_signoff_schema(payload)
    assert valid is True
    assert violations == []


def test_uat_signoff_schema_validation_violations():
    # Not a dict
    assert validate_uat_signoff_schema("not-dict")[0] is False
    # Missing signoffs key
    assert validate_uat_signoff_schema({})[0] is False

    # Entry not dict
    assert validate_uat_signoff_schema({"signoffs": {"k": "not-dict"}})[0] is False

    # Bad fields
    bad_entry = {
        "signoffs": {
            "bad": {
                "outcome_id": "",
                "prd_id": "INVALID",
                "status": "UnknownStatus",
                "reviewer": "invalid reviewer string ;;\n",
                "timestamp": "not-a-timestamp",
                "test_correlation": "not-dict",
            }
        }
    }
    valid, violations = validate_uat_signoff_schema(bad_entry)
    assert valid is False
    assert len(violations) >= 5

    # Test correlation missing fields
    bad_tc = {
        "signoffs": {
            "PRD-0001:1": {
                "outcome_id": "1",
                "prd_id": "PRD-0001",
                "status": "Pending",
                "reviewer": "Taylor <taylor@example.com>",
                "timestamp": "2026-09-29T18:00:00Z",
                "test_correlation": {"scenario": 123},
            }
        }
    }
    valid_tc, v_tc = validate_uat_signoff_schema(bad_tc)
    assert valid_tc is False
    assert any("test_correlation" in v for v in v_tc)


def test_reconcile_signoffs_tie_breaking_and_invalid():
    # Invalid payloads fallback to empty
    res = reconcile_signoffs({}, {})
    assert res["signoffs"] == {}

    # Equal timestamps tie-broken by reviewer string
    ts = "2026-09-29T18:00:00Z"
    base = {
        "signoffs": {
            "PRD-0003:1": {
                "outcome_id": "1",
                "prd_id": "PRD-0003",
                "status": "Approved",
                "reviewer": "Alice <alice@example.com>",
                "timestamp": ts,
            }
        }
    }
    incoming = {
        "signoffs": {
            "PRD-0003:1": {
                "outcome_id": "1",
                "prd_id": "PRD-0003",
                "status": "Rejected",
                "reviewer": "Bob <bob@example.com>",
                "timestamp": ts,
            }
        }
    }
    merged = reconcile_signoffs(base, incoming)
    # Bob > Alice alphabetically, so Bob wins
    assert merged["signoffs"]["PRD-0003:1"]["reviewer"] == "Bob <bob@example.com>"
    assert merged["signoffs"]["PRD-0003:1"]["status"] == "Rejected"


def test_map_outcomes_to_tests_all_statuses():
    # Empty PRD outcomes
    assert extract_prd_outcomes("# PRD without outcomes\n") == []
    assert compute_delivery_readiness([]) == 0.0

    stories = [
        {"id": "0046", "governing_prd": "PRD-0003", "scenarios": ["Scenario: A", "Scenario: B"]},
    ]

    # Scenario: all pass
    m_pass = map_outcomes_to_tests(SAMPLE_PRD, "PRD-0003", stories, {"Scenario: A": "passed", "Scenario: B": "passed"})
    assert m_pass[0].test_status == "Passed (CI)"

    # Scenario: one fails
    m_fail = map_outcomes_to_tests(SAMPLE_PRD, "PRD-0003", stories, {"Scenario: A": "passed", "Scenario: B": "failed"})
    assert m_fail[0].test_status == "Failed (CI)"

    # Scenario: pending
    m_pend = map_outcomes_to_tests(SAMPLE_PRD, "PRD-0003", stories, {"Scenario: A": "pending", "Scenario: B": "passed"})
    assert m_pend[0].test_status == "Pending (CI)"

    # No scenarios for outcome
    m_none = map_outcomes_to_tests(SAMPLE_PRD, "PRD-0003", [], {})
    assert m_none[0].test_status == "Pending (No Tests)"

    # Readiness
    assert compute_delivery_readiness(m_pass) == 0.0  # Not approved yet
    m_pass[0].uat_status = "Approved"
    assert compute_delivery_readiness(m_pass) == 50.0  # 1 of 2 approved and passed


def test_manifest_verification_edge_cases(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)

    gi = repo / ".gitignore"
    gi.write_text("dist/\n", encoding="utf-8")
    f = repo / "main.py"
    f.write_text("print('hello')\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore", "main.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "init"], cwd=repo, check=True)

    manifest_file = repo / "dist" / "releases" / "PRD-0001-release-manifest.json"
    manifest = generate_release_manifest(
        repo_root=repo,
        prd_id="PRD-0001",
        prd_title="Core Architecture",
        target_persona="Jordan",
        completed_tasks=[{"id": "TASK-0001", "commit_sha": "abc1234"}],
        test_summary={"status": "Passed (CI)", "total_scenarios": 1, "failed_scenarios": 0},
        uat_summary={"status": "Approved", "total_outcomes": 1, "approved_outcomes": 1},
        output_path=manifest_file,
    )
    assert manifest_file.is_file()

    # Verify from file path
    valid, issues = verify_release_manifest(manifest_file, repo)
    assert valid is True

    # Bad input types
    assert verify_release_manifest(12345, repo)[0] is False
    assert verify_release_manifest(tmp_path / "nonexistent.json", repo)[0] is False

    # Malformed JSON
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not valid json", encoding="utf-8")
    assert verify_release_manifest(bad_json, repo)[0] is False

    # Missing fields
    assert verify_release_manifest({}, repo)[0] is False

    # Failing test verification
    failing_manifest = dict(manifest)
    failing_manifest["test_verification"] = {"status": "Failed (CI)", "failed_scenarios": 1}
    failing_manifest["manifest_signature"] = compute_manifest_signature(
        "PRD-0001",
        manifest["verified_tree_digest"],
        manifest["completed_tasks"],
        {"status": "Failed (CI)", "failed_scenarios": 1},
        manifest["uat_verification"],
    )
    v_fail, i_fail = verify_release_manifest(failing_manifest, repo)
    assert v_fail is False
    assert any("test verification failure" in i.lower() for i in i_fail)
