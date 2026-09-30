"""Executable benchmark and validation suite for SPIKE-0040.

Hypothesis: A tamper-evident, version-locked sign-off receipt format stored directly in git
(docs/project/product/uat-signoff.json) binding passing BDD test runs, reviewer identity,
timestamps, and an exact SHA-256 git tree digest into a cryptographic release manifest
(dist/releases/PRD-XXXX-release-manifest.json) provides merge-conflict-resilient concurrent
PM sign-offs, zero external crypto dependencies, and headless verification in <50ms.
"""

from __future__ import annotations

import datetime
import importlib
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from spec_ops.prd.manifest import (
    compute_git_tree_digest,
    compute_manifest_signature,
    generate_release_manifest,
    verify_release_manifest,
)
from spec_ops.prd.uat_receipt import (
    OutcomeTestMapping,
    compute_delivery_readiness,
    extract_prd_outcomes,
    map_outcomes_to_tests,
    reconcile_signoffs,
    serialize_canonical_json,
    validate_uat_signoff_schema,
)

from .harness import SAMPLE_PRD_CONTENT, record_findings, run_benchmark


def test_hypothesis_benchmark(tmp_path: Path):
    """Asserts that headless cryptographic verification and operations achieve <50ms p95 latency."""
    harness_dir = Path(__file__).parent
    results = run_benchmark(iterations=25, repo_root=Path.cwd())

    # Record findings to disk for ADR graduation
    findings_str = results["findings"]
    record_findings(harness_dir, findings_str)

    assert results["status"] == "completed"
    assert results["p95_latency_ms"] < 50.0, (
        f"p95 latency was {results['p95_latency_ms']}ms, exceeding 50ms budget"
    )
    assert results["avg_tree_ms"] < 30.0
    assert results["avg_verify_ms"] < 30.0


def test_zero_external_crypto_dependencies():
    """Asserts that manifest and UAT verification rely strictly on standard library hashlib."""
    import spec_ops.prd.manifest as manifest_mod
    import spec_ops.prd.uat_receipt as uat_mod

    manifest_source = Path(manifest_mod.__file__).read_text(encoding="utf-8")
    uat_source = Path(uat_mod.__file__).read_text(encoding="utf-8")

    forbidden = ["cryptography", "nacl", "Crypto", "paramiko", "jose", "jwt"]
    for pkg in forbidden:
        assert f"import {pkg}" not in manifest_source
        assert f"from {pkg}" not in manifest_source
        assert f"import {pkg}" not in uat_source
        assert f"from {pkg}" not in uat_source

    assert "hashlib" in manifest_source


def test_tamper_evident_tree_and_manifest_invalidation(tmp_path: Path):
    """Verifies that disk tampering or uncommitted diffs invalidate release manifest verification."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)

    gi = repo / ".gitignore"
    gi.write_text("dist/\n", encoding="utf-8")
    f1 = repo / "feature.py"
    f1.write_text("print('feature 1')\n", encoding="utf-8")
    subprocess.run(["git", "add", ".gitignore", "feature.py"], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "add feature and gitignore"], cwd=repo, check=True)

    completed_tasks = [{"id": "TASK-0040", "commit_sha": "abc1234"}]
    test_summary = {"status": "Passed (CI)", "total_scenarios": 5, "failed_scenarios": 0}
    uat_summary = {"status": "Approved", "total_outcomes": 2, "approved_outcomes": 2}

    manifest = generate_release_manifest(
        repo_root=repo,
        prd_id="PRD-0003",
        prd_title="Living UAT",
        target_persona="Taylor",
        completed_tasks=completed_tasks,
        test_summary=test_summary,
        uat_summary=uat_summary,
        output_path=repo / "dist" / "releases" / "PRD-0003-release-manifest.json",
    )

    # 1. Clean state verifies successfully
    valid, issues = verify_release_manifest(manifest, repo)
    assert valid is True
    assert issues == []

    # 2. Tampering: Uncommitted diffs
    f1.write_text("print('tampered content')\n", encoding="utf-8")
    valid_tampered, issues_tampered = verify_release_manifest(manifest, repo)
    assert valid_tampered is False
    assert any("uncommitted diffs" in issue.lower() or "dirty" in issue.lower() for issue in issues_tampered)

    # 3. Tampering: Commit the tampered file (tree digest changed)
    subprocess.run(["git", "commit", "-am", "tampered commit"], cwd=repo, check=True)
    valid_committed, issues_committed = verify_release_manifest(manifest, repo)
    assert valid_committed is False
    assert any("tampering detected" in issue.lower() or "tree sha-256" in issue.lower() for issue in issues_committed)

    # 4. Tampering: Manifest signature corrupted
    corrupt_manifest = dict(manifest)
    corrupt_manifest["manifest_signature"] = "deadbeef" * 8
    # Revert repo to clean matching commit
    subprocess.run(["git", "reset", "--hard", "HEAD~1"], cwd=repo, check=True)
    valid_corrupt, issues_corrupt = verify_release_manifest(corrupt_manifest, repo)
    assert valid_corrupt is False
    assert any("signature invalid" in issue.lower() for issue in issues_corrupt)

    # 5. Missing UAT approval
    unapproved_manifest = dict(manifest)
    unapproved_manifest["uat_verification"] = {"status": "Pending PM"}
    # Recompute signature for unapproved to isolate UAT check
    unapproved_manifest["manifest_signature"] = compute_manifest_signature(
        "PRD-0003",
        manifest["verified_tree_digest"],
        completed_tasks,
        test_summary,
        {"status": "Pending PM"},
    )
    valid_unapproved, issues_unapproved = verify_release_manifest(unapproved_manifest, repo)
    assert valid_unapproved is False
    assert any("mandatory pm uat approval required" in issue.lower() for issue in issues_unapproved)


def test_concurrent_pm_signoff_merge_resilience():
    """Asserts that concurrent PM sign-offs reconcile with Last-Write-Wins and history preservation."""
    taylor_base = {
        "$schema": "spec-ops/uat-signoff-v1",
        "version": "1.0",
        "signoffs": {
            "PRD-0003:1": {
                "outcome_id": "1",
                "prd_id": "PRD-0003",
                "status": "Approved",
                "reviewer": "Taylor <taylor@example.com>",
                "timestamp": "2026-09-29T18:00:00Z",
                "notes": "Verified initial workflow",
            },
        },
    }

    jordan_incoming = {
        "$schema": "spec-ops/uat-signoff-v1",
        "version": "1.0",
        "signoffs": {
            "PRD-0003:2": {
                "outcome_id": "2",
                "prd_id": "PRD-0003",
                "status": "Approved",
                "reviewer": "Jordan <jordan@example.com>",
                "timestamp": "2026-09-29T18:05:00Z",
                "notes": "Verified CI pipeline gate integration",
            },
            "PRD-0003:1": {
                "outcome_id": "1",
                "prd_id": "PRD-0003",
                "status": "Approved",
                "reviewer": "Taylor <taylor@example.com>",
                "timestamp": "2026-09-29T18:15:00Z",
                "notes": "Verified multi-browser compatibility",
            },
        },
    }

    merged = reconcile_signoffs(taylor_base, jordan_incoming)
    assert "PRD-0003:1" in merged["signoffs"]
    assert "PRD-0003:2" in merged["signoffs"]

    # PRD-0003:1 has latest timestamp (18:15:00Z) and updated notes
    item1 = merged["signoffs"]["PRD-0003:1"]
    assert item1["timestamp"] == "2026-09-29T18:15:00Z"
    assert item1["notes"] == "Verified multi-browser compatibility"
    # History preserved
    assert len(item1["history"]) == 2
    assert item1["history"][0]["timestamp"] == "2026-09-29T18:00:00Z"
    assert item1["history"][1]["timestamp"] == "2026-09-29T18:15:00Z"


def test_outcome_to_test_mapping_engine():
    """Asserts that PRD outcomes map accurately to Gherkin scenarios and CI test results."""
    outcomes = extract_prd_outcomes(SAMPLE_PRD_CONTENT)
    assert len(outcomes) == 3
    assert outcomes[0][0] == "1"

    stories = [
        {"id": "0043", "governing_prd": "PRD-0003", "scenarios": ["Scenario: Web Studio Launch"]},
        {"id": "0046", "governing_prd": "PRD-0003", "scenarios": ["Scenario: UAT Matrix"]},
        {"id": "0100", "governing_prd": "PRD-0003", "scenarios": ["Scenario: PRD Shipping"]},
    ]
    test_results = {
        "Scenario: Web Studio Launch": "passed",
        "Scenario: UAT Matrix": "passed",
        "Scenario: PRD Shipping": "failed",
    }
    existing_signoffs = {
        "signoffs": {
            "PRD-0003:1": {"status": "Approved", "reviewer": "Taylor <taylor@example.com>"},
            "PRD-0003:2": {"status": "Pending PM", "reviewer": ""},
        }
    }

    mappings = map_outcomes_to_tests(
        SAMPLE_PRD_CONTENT,
        "PRD-0003",
        stories,
        test_results,
        existing_signoffs=existing_signoffs,
    )
    assert len(mappings) == 3
    assert mappings[0].test_status == "Failed (CI)"  # Because PRD Shipping failed among linked stories
    assert mappings[0].uat_status == "Approved"

    readiness = compute_delivery_readiness(mappings)
    assert isinstance(readiness, float)


# --- Hypothesis Property Tests ---

@given(
    st.dictionaries(
        keys=st.text(min_size=1, max_size=10, alphabet="abcdefghijklmnopqrstuvwxyz"),
        values=st.integers(min_value=0, max_value=1000),
        min_size=1,
        max_size=15,
    )
)
@settings(max_examples=50)
def test_canonical_json_serialization_deterministic(d: dict[str, int]):
    """Property: Canonical JSON serialization is bit-exact invariant to key insertion order."""
    # Reverse keys order
    rev_d = {k: d[k] for k in reversed(list(d.keys()))}
    s1 = serialize_canonical_json(d)
    s2 = serialize_canonical_json(rev_d)
    assert s1 == s2
    assert s1.endswith("\n")


@given(
    st.lists(
        st.tuples(
            st.sampled_from(["PRD-0001", "PRD-0002", "PRD-0003"]),
            st.sampled_from(["1", "2", "3", "4"]),
            st.sampled_from(["Approved", "Pending", "Rejected"]),
            st.sampled_from(["Taylor <taylor@example.com>", "Jordan <jordan@example.com>"]),
            st.integers(min_value=1600000000, max_value=1800000000),
        ),
        min_size=1,
        max_size=10,
    )
)
@settings(max_examples=40)
def test_reconcile_signoffs_idempotency_and_sorting(entries: list[tuple[str, str, str, str, int]]):
    """Property: Sign-off reconciliation is idempotent and produces valid, deterministically sorted JSON."""
    signoffs: dict[str, Any] = {}
    for prd_id, out_id, status, reviewer, epoch in entries:
        dt = datetime.datetime.fromtimestamp(epoch, datetime.timezone.utc).isoformat()
        key = f"{prd_id}:{out_id}"
        signoffs[key] = {
            "outcome_id": out_id,
            "prd_id": prd_id,
            "status": status,
            "reviewer": reviewer,
            "timestamp": dt,
            "notes": f"Note for {key}",
        }

    payload = {
        "$schema": "spec-ops/uat-signoff-v1",
        "version": "1.0",
        "signoffs": signoffs,
    }

    # Invariant: Reconciling with self is idempotent
    merged = reconcile_signoffs(payload, payload)
    assert sorted(merged["signoffs"].keys()) == sorted(signoffs.keys())
    assert serialize_canonical_json(merged) == serialize_canonical_json(reconcile_signoffs(merged, merged))

    # Invariant: Output validates under schema
    valid, violations = validate_uat_signoff_schema(merged)
    assert valid is True, f"Violations: {violations}"
