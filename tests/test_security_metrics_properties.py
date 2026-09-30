"""Generative property-based tests for security posture and compliance metrics (ADR-0009)."""

from __future__ import annotations

from typing import Any

from hypothesis import given
from hypothesis import strategies as st

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
)


@given(
    signed_count=st.integers(min_value=-10, max_value=500),
    total_count=st.integers(min_value=-10, max_value=500),
)
def test_signed_commit_coverage_mathematical_bounds(signed_count: int, total_count: int) -> None:
    """Property: Commit coverage percentage is always strictly bounded between 0.0% and 100.0%."""
    rate = calculate_signed_commit_coverage(signed_count, total_count)
    assert 0.0 <= rate <= 100.0
    if total_count <= 0:
        assert rate == 100.0
    elif signed_count <= 0:
        assert rate == 0.0
    elif signed_count >= total_count:
        assert rate == 100.0


@given(
    signed_off_count=st.integers(min_value=-10, max_value=500),
    total_count=st.integers(min_value=-10, max_value=500),
)
def test_human_signoff_rate_mathematical_bounds(signed_off_count: int, total_count: int) -> None:
    """Property: Human sign-off rate percentage is always strictly bounded between 0.0% and 100.0%."""
    rate = calculate_human_signoff_rate(signed_off_count, total_count)
    assert 0.0 <= rate <= 100.0
    if total_count <= 0:
        assert rate == 100.0
    elif signed_off_count <= 0:
        assert rate == 0.0
    elif signed_off_count >= total_count:
        assert rate == 100.0


@given(
    violations_count=st.integers(min_value=0, max_value=100),
)
def test_secret_scan_status_evaluation(violations_count: int) -> None:
    """Property: Secret scan status is deterministically Pass when clean, else Fail."""
    status = evaluate_secret_scan_status(violations_count)
    assert status in ("Pass", "Fail")
    if violations_count == 0:
        assert status == "Pass"
    else:
        assert status == "Fail"


@given(is_valid=st.booleans())
def test_lockfile_integrity_evaluation(is_valid: bool) -> None:
    """Property: Lockfile integrity is Synchronized when valid, else Modified."""
    status = evaluate_lockfile_integrity(is_valid)
    assert status in ("Synchronized", "Modified")
    if is_valid:
        assert status == "Synchronized"
    else:
        assert status == "Modified"


cve_strategy = st.fixed_dictionaries({
    "advisory_id": st.text(min_size=1, max_size=20),
    "severity": st.sampled_from(["low", "LOW", "medium", "MED", "moderate", "high", "HIGH", "critical", "CRITICAL"]),
    "package": st.text(min_size=1, max_size=20),
})


@given(cves=st.lists(cve_strategy, max_size=50))
def test_vulnerability_counts_aggregation(cves: list[dict[str, Any]]) -> None:
    """Property: Aggregated vulnerability counts preserve total items and non-negative partition."""
    counts = aggregate_vulnerability_counts(cves)
    assert counts["total"] == len(cves)
    assert counts["low"] >= 0
    assert counts["med"] >= 0
    assert counts["high"] >= 0
    assert counts["low"] + counts["med"] + counts["high"] == counts["total"]

    indicator = format_vulnerability_indicator(counts)
    assert f"{counts['low']} Low" in indicator
    assert f"{counts['med']} Med" in indicator
    assert f"{counts['high']} High" in indicator


task_strategy = st.fixed_dictionaries({
    "id": st.from_regex(r"^TASK-[0-9]{4}$"),
    "title": st.text(min_size=1, max_size=40),
    "target_bc": st.sampled_from(["security", "core", "visualizer", "backlog", ""]),
    "has_human_signoff": st.booleans(),
    "has_signed_commits": st.booleans(),
    "cve_count": st.integers(min_value=0, max_value=5),
})


@given(
    tasks=st.lists(task_strategy, max_size=40),
    secret_clean=st.booleans(),
    lockfile_clean=st.booleans(),
    cves=st.lists(cve_strategy, max_size=20),
)
def test_project_compliance_aggregation_invariants(
    tasks: list[dict[str, Any]],
    secret_clean: bool,
    lockfile_clean: bool,
    cves: list[dict[str, Any]],
) -> None:
    """Property: Project compliance aggregation maintains mathematical invariants across randomized inputs."""
    posture = aggregate_project_compliance(
        tasks=tasks,
        secret_clean=secret_clean,
        lockfile_clean=lockfile_clean,
        cves=cves,
    )

    # 1. Bounded rates
    assert 0.0 <= posture["signed_commit_coverage"] <= 100.0
    assert 0.0 <= posture["human_signoff_rate"] <= 100.0

    # 2. Partitions sum to total
    assert posture["total_tasks"] == len(tasks)
    assert posture["compliant_count"] + posture["non_compliant_count"] == len(tasks)
    assert len(posture["triage_tasks"]) == len(tasks)

    # 3. Indicator strings
    assert posture["secret_scan_status"] in ("Pass", "Fail")
    assert posture["lockfile_integrity"] in ("Synchronized", "Modified")
    assert f"{posture['signed_commit_coverage']}%" == posture["signed_commit_coverage_display"]
    assert f"{posture['human_signoff_rate']}%" == posture["human_signoff_rate_display"]

    # 4. Task-level consistency
    for t in posture["triage_tasks"]:
        is_compliant = t["is_compliant"]
        missing = t["missing_artifacts"]
        assert is_compliant == (len(missing) == 0)
        expected_compliant = t["has_human_signoff"] and t["has_signed_commits"] and (t["cve_count"] == 0)
        assert is_compliant == expected_compliant
        if not t["has_human_signoff"]:
            assert "Human Review Sign-off" in missing
        if not t["has_signed_commits"]:
            assert "Cryptographic Commit Signature" in missing
        if t["cve_count"] > 0:
            assert any("Open CVE" in m for m in missing)
