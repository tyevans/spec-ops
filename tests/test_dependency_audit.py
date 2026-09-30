"""Unit tests for dependency audit, license policies, OSV client, and waiver gating."""

from __future__ import annotations

import datetime
import json
from pathlib import Path

import pytest

from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.config.models import LicenseSettings, SecuritySettings, SpecOpsConfig
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project
from spec_ops.security.audit import run_dependency_audit
from spec_ops.security.cve.osv_client import (
    Vulnerability,
    audit_dependencies_cve,
    classify_severity,
    parse_cvss_score,
    query_osv_vulnerabilities,
)
from spec_ops.security.licenses.policy import (
    STANDARD_PROFILES,
    audit_dependencies_licenses,
    extract_repo_dependencies,
    is_license_allowed,
    normalize_license,
    resolve_package_license,
)
from spec_ops.security.waivers import (
    Waiver,
    compute_waiver_signature,
    find_active_waiver,
    is_waiver_expired,
    load_waivers,
    normalize_waiver_id,
    parse_waiver_content,
    parse_waiver_date,
    parse_waiver_file,
    verify_waiver_signature,
)


def test_normalize_license():
    assert normalize_license("MIT") == "MIT"
    assert normalize_license("mit license") == "MIT"
    assert normalize_license("Apache 2.0") == "Apache-2.0"
    assert normalize_license("bsd 3-clause") == "BSD-3-Clause"
    assert normalize_license("AGPLv3") == "AGPL-3.0"
    assert normalize_license("gnu affero general public license") == "AGPL-3.0"
    assert normalize_license("GPLv3") == "GPL-3.0"
    assert normalize_license("custom-license") == "custom-license"
    assert normalize_license("") == "UNKNOWN"
    assert normalize_license(None) == "UNKNOWN"


def test_is_license_allowed():
    allowed = ["MIT", "Apache-2.0", "BSD-3-Clause"]
    assert is_license_allowed("MIT", allowed) is True
    assert is_license_allowed("mit license", allowed) is True
    assert is_license_allowed("Apache-2.0", allowed) is True
    assert is_license_allowed("AGPL-3.0", allowed) is False
    assert is_license_allowed("GPL-3.0", allowed) is False


def test_resolve_package_license(tmp_path: Path):
    # From package record
    assert resolve_package_license("pkg1", {"license": "MIT"}) == "MIT"

    # From local json cache
    cache_dir = tmp_path / ".spec-ops"
    cache_dir.mkdir(parents=True)
    (cache_dir / "licenses.json").write_text(
        json.dumps({"packages": {"cached-pkg": "Apache-2.0"}}),
        encoding="utf-8",
    )
    assert resolve_package_license("cached-pkg", {}, repo_dir=tmp_path) == "Apache-2.0"

    # Heuristics
    assert resolve_package_license("some-agpl-pkg", {}) == "AGPL-3.0"
    assert resolve_package_license("gpl-helper", {}) == "GPL-3.0"
    assert resolve_package_license("unknown-xyz-abc", {}) == "UNKNOWN"


def test_classify_severity():
    assert classify_severity(9.8) == "CRITICAL"
    assert classify_severity(7.5) == "HIGH"
    assert classify_severity(5.0) == "MEDIUM"
    assert classify_severity(2.0) == "LOW"
    assert classify_severity(0.0, "HIGH") == "HIGH"
    assert classify_severity(0.0, "MODERATE") == "MEDIUM"
    assert classify_severity(0.0, "UNKNOWN") == "UNKNOWN"


def test_parse_cvss_score():
    assert parse_cvss_score(8.5) == 8.5
    assert parse_cvss_score("8.5") == 8.5
    assert parse_cvss_score("CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H 9.1") == 9.1
    assert parse_cvss_score("invalid") == 0.0


def test_waiver_normalization_and_parsing():
    assert normalize_waiver_id("1") == "WAIVER-001"
    assert normalize_waiver_id("WAIVER-2") == "WAIVER-002"
    assert normalize_waiver_id("WAIVER-1234") == "WAIVER-1234"

    with pytest.raises(ValueError):
        normalize_waiver_id("")
    with pytest.raises(ValueError):
        normalize_waiver_id(None)
    with pytest.raises(ValueError):
        normalize_waiver_id("invalid spaces !!")

    d = datetime.date(2027, 5, 20)
    assert parse_waiver_date(d) == d
    assert parse_waiver_date(datetime.datetime(2027, 5, 20, 10, 0)) == d
    assert parse_waiver_date("2027-05-20") == d
    assert parse_waiver_date("2027-05-20T12:00:00") == d

    with pytest.raises(ValueError):
        parse_waiver_date("not-a-date")
    with pytest.raises(ValueError):
        parse_waiver_date(12345)


def test_waiver_signature_and_expiration():
    wid = "WAIVER-001"
    pkg = "test-pkg"
    signer = "Sasha"
    exp = datetime.date(2028, 1, 1)

    sig = compute_waiver_signature(wid, pkg, signer, exp)
    w = Waiver(id=wid, package=pkg, signer=signer, expires=exp, signature=sig)

    assert verify_waiver_signature(w) is True
    assert is_waiver_expired(w, reference_date=datetime.date(2027, 1, 1)) is False
    assert is_waiver_expired(w, reference_date=datetime.date(2029, 1, 1)) is True

    # Bad signature
    w_bad = Waiver(id=wid, package=pkg, signer=signer, expires=exp, signature="corrupted")
    assert verify_waiver_signature(w_bad) is False


def test_load_and_find_active_waiver(tmp_path: Path):
    waiver_dir = tmp_path / "waivers"
    waiver_dir.mkdir()

    # Create active waiver
    sig = compute_waiver_signature("WAIVER-001", "my-pkg", "Sasha", "2029-01-01")
    content = f"""---
id: WAIVER-001
package: my-pkg
license: AGPL-3.0
signer: Sasha
expires: 2029-01-01
signature: {sig}
status: Approved
---
"""
    (waiver_dir / "WAIVER-001.md").write_text(content, encoding="utf-8")

    waivers = load_waivers(waiver_dir)
    assert len(waivers) == 1
    assert waivers[0].id == "WAIVER-001"

    found = find_active_waiver(
        waivers,
        package="my-pkg",
        license_id="AGPL-3.0",
        reference_date=datetime.date(2026, 1, 1),
    )
    assert found is not None
    assert found.id == "WAIVER-001"

    # Mismatched license
    assert find_active_waiver(waivers, package="my-pkg", license_id="GPL-3.0") is None
    # Expired
    assert find_active_waiver(waivers, package="my-pkg", license_id="AGPL-3.0", reference_date=datetime.date(2030, 1, 1)) is None


def test_osv_cache_query(tmp_path: Path):
    cache_dir = tmp_path / ".spec-ops"
    cache_dir.mkdir(parents=True)
    cache_data = {
        "packages": {
            "demo-pkg": [
                {
                    "id": "GHSA-1234",
                    "aliases": ["CVE-2026-0001"],
                    "version": "1.0.0",
                    "cvss_score": 9.2,
                    "severity": "CRITICAL",
                    "fixed_version": "1.0.2",
                    "summary": "Critical flaw",
                }
            ]
        }
    }
    (cache_dir / "cve_cache.json").write_text(json.dumps(cache_data), encoding="utf-8")

    vulns = query_osv_vulnerabilities("demo-pkg", "1.0.0", repo_dir=tmp_path)
    assert len(vulns) == 1
    assert vulns[0].advisory_id == "GHSA-1234"
    assert vulns[0].severity == "CRITICAL"
    assert vulns[0].fixed_version == "1.0.2"


def test_run_dependency_audit_clean_repo(tmp_path: Path):
    init_project(name="CleanAuditRepo", target_dir=tmp_path)
    (tmp_path / "uv.lock").write_text('version = 1\nrevision = 1\nrequires-python = ">=3.13"\n', encoding="utf-8")

    report = run_dependency_audit(tmp_path, offline=True)
    assert report.ok is True
    assert len(report.unwaived_vulnerabilities) == 0
    assert len(report.unwaived_license_violations) == 0


def test_run_dependency_audit_with_unwaived_violations(tmp_path: Path):
    init_project(name="ViolatingAuditRepo", target_dir=tmp_path)

    # Config restricts licenses
    (tmp_path / "specops.toml").write_text(
        '[project]\nname = "ViolatingAuditRepo"\n\n[security.licenses]\nallowed = ["MIT"]\n',
        encoding="utf-8",
    )

    # Lockfile with AGPL dependency
    (tmp_path / "uv.lock").write_text(
        'version = 1\nrevision = 1\nrequires-python = ">=3.13"\n\n'
        '[[package]]\nname = "bad-license-lib"\nversion = "1.0.0"\nlicense = "AGPL-3.0"\n',
        encoding="utf-8",
    )

    report = run_dependency_audit(tmp_path, offline=True)
    assert report.ok is False
    assert len(report.unwaived_license_violations) == 1
    assert report.unwaived_license_violations[0].package == "bad-license-lib"
    assert "non-compliant license" in report.errors[0].lower()


def test_queue_gating_blocks_refinement_and_completion(tmp_path: Path):
    init_project(name="GateTestRepo", target_dir=tmp_path)
    cfg = SpecOpsConfig(
        root_dir=tmp_path,
        security=SecuritySettings(
            licenses=LicenseSettings(allowed=["MIT"]),
            allowed_licenses=["MIT"],
        ),
    )
    (tmp_path / "specops.toml").write_text(
        '[project]\nname = "GateTestRepo"\n\n[security.licenses]\nallowed = ["MIT"]\n',
        encoding="utf-8",
    )
    # Add violating dependency
    (tmp_path / "uv.lock").write_text(
        'version = 1\nrevision = 1\nrequires-python = ">=3.13"\n\n'
        '[[package]]\nname = "restricted-pkg"\nversion = "1.0.0"\nlicense = "AGPL-3.0"\n',
        encoding="utf-8",
    )

    queue = BacklogQueue(cfg.backlog_dir)
    task_file = queue.proposed_dir / "0099-gated-task.md"
    task = Task(
        id="0099",
        title="Gated Task",
        status="Proposed",
        target_bc="security",
        allows_dependencies=True,
        file_path=task_file,
    )
    write_task_file(task)

    # Refinement gate fails
    ok_refine, msg_refine = queue.refine_task_with_gate(task, repo_root=tmp_path)
    assert ok_refine is False
    assert "refinement gate failed" in msg_refine.lower()
