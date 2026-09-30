"""Executable BDD scenarios for US-0057 and US-0112: Dependency Vulnerability and License Policy Gating."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.backlog.queue import BacklogQueue, write_task_file
from spec_ops.config.loader import load_config
from spec_ops.core.models import Task
from spec_ops.scaffold.init import init_project
from spec_ops.security.waivers import compute_waiver_signature

SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
CLI_ENV = {
    **os.environ,
    "PYTHONPATH": f"{SRC_DIR}:{os.environ.get('PYTHONPATH', '')}".rstrip(":"),
    "PATH": f"{Path(sys.executable).parent}:{os.environ.get('PATH', '')}",
}

scenarios(
    "features/us_0057_automated_dependency_vulnerability_scanning.feature",
    "features/us_0112_automated_dependency_vulnerability_license_policy_gating.feature",
)


@pytest.fixture
def bdd_sec_ctx(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()

    init_project(name="SecAuditApp", target_dir=repo, profiles=["core", "bdd", "ddd", "security"])

    # Create base pyproject.toml and uv.lock
    pyproject_content = (
        '[project]\nname = "sec-audit-app"\nversion = "0.1.0"\n'
        'requires-python = ">=3.13"\ndependencies = []\n'
    )
    (repo / "pyproject.toml").write_text(pyproject_content, encoding="utf-8")
    (repo / "uv.lock").write_text('version = 1\nrevision = 1\nrequires-python = ">=3.13"\n', encoding="utf-8")

    # Initialize git repository
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Security Officer"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "security@specops.dev"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    cfg = load_config(repo)
    return {
        "repo": repo,
        "config": cfg,
        "queue": BacklogQueue(cfg.backlog_dir),
        "cli_res": None,
        "task": None,
    }


# ==============================================================================
# Scenario: Blocking tasks that introduce dependencies with High or Critical CVEs
# ==============================================================================


@given("a project lockfile containing a package version with an active High or Critical CVE reported in the OSV database")
def lockfile_with_high_cve(bdd_sec_ctx: dict[str, Any]):
    repo: Path = bdd_sec_ctx["repo"]
    lock_file = repo / "uv.lock"
    content = (
        'version = 1\nrevision = 1\nrequires-python = ">=3.13"\n\n'
        '[[package]]\nname = "vulnerable-lib"\nversion = "1.0.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
    )
    lock_file.write_text(content, encoding="utf-8")

    # Populate local vulnerability cache simulating OSV database record
    cache_dir = repo / ".spec-ops"
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / "cve_cache.json"
    cache_data = {
        "vulnerable-lib": [
            {
                "id": "GHSA-test-9999",
                "aliases": ["CVE-2026-1234"],
                "version": "1.0.0",
                "cvss_score": 8.5,
                "severity": "HIGH",
                "fixed_version": "1.0.1",
                "summary": "Remote buffer overflow vulnerability",
            }
        ]
    }
    cache_file.write_text(json.dumps(cache_data), encoding="utf-8")


@when('"spec-ops audit dependencies" executes during preflight or CI verification')
def run_audit_dependencies_cli(bdd_sec_ctx: dict[str, Any]):
    repo: Path = bdd_sec_ctx["repo"]
    cmd = [sys.executable, "-m", "spec_ops.cli.main", "audit", "dependencies", "--path", str(repo)]
    res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, env=CLI_ENV)
    bdd_sec_ctx["cli_res"] = res


@then("the command exits with returncode 1")
def assert_exit_code_1(bdd_sec_ctx: dict[str, Any]):
    res = bdd_sec_ctx["cli_res"]
    assert res is not None, "CLI command did not run"
    assert res.returncode == 1, f"Expected returncode 1, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"


@then("lists the vulnerable package name, advisory ID, severity, and minimum remediating version.")
def assert_cve_details_short(bdd_sec_ctx: dict[str, Any]):
    res = bdd_sec_ctx["cli_res"]
    out = (res.stdout + res.stderr).lower()
    assert "vulnerable-lib" in out
    assert "ghsa-test-9999" in out or "cve-2026-1234" in out
    assert "high" in out
    assert "1.0.1" in out


@then("lists the vulnerable package name, advisory ID (GHSA/CVE), CVSS score, severity level, and minimum remediating version.")
def assert_cve_details_full(bdd_sec_ctx: dict[str, Any]):
    res = bdd_sec_ctx["cli_res"]
    out = (res.stdout + res.stderr).lower()
    assert "vulnerable-lib" in out
    assert "ghsa-test-9999" in out or "cve-2026-1234" in out
    assert "8.5" in out
    assert "high" in out
    assert "1.0.1" in out


# ==============================================================================
# Scenario: Enforcing open-source software license policy
# ==============================================================================


@given('"specops.toml" configures allowed_licenses = ["MIT", "Apache-2.0", "BSD-3-Clause"]')
def configure_top_level_allowed_licenses(bdd_sec_ctx: dict[str, Any]):
    repo: Path = bdd_sec_ctx["repo"]
    config_file = repo / "specops.toml"
    current = config_file.read_text(encoding="utf-8") if config_file.exists() else ""
    updated = current + '\nallowed_licenses = ["MIT", "Apache-2.0", "BSD-3-Clause"]\n'
    config_file.write_text(updated, encoding="utf-8")


@given('"specops.toml" configures "[security.licenses] allowed = [\'MIT\', \'Apache-2.0\', \'BSD-3-Clause\']"')
def configure_nested_allowed_licenses(bdd_sec_ctx: dict[str, Any]):
    repo: Path = bdd_sec_ctx["repo"]
    config_file = repo / "specops.toml"
    current = config_file.read_text(encoding="utf-8") if config_file.exists() else ""
    updated = current + '\n[security.licenses]\nallowed = ["MIT", "Apache-2.0", "BSD-3-Clause"]\n'
    config_file.write_text(updated, encoding="utf-8")


@when('an autonomous worker or developer adds a dependency with an incompatible license such as "AGPL-3.0"')
def add_incompatible_dependency(bdd_sec_ctx: dict[str, Any]):
    repo: Path = bdd_sec_ctx["repo"]
    lock_file = repo / "uv.lock"
    content = (
        'version = 1\nrevision = 1\nrequires-python = ">=3.13"\n\n'
        '[[package]]\nname = "copyleft-lib"\nversion = "2.0.0"\n'
        'license = "AGPL-3.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
    )
    lock_file.write_text(content, encoding="utf-8")

    # Author candidate task
    queue: BacklogQueue = bdd_sec_ctx["queue"]
    task_file = queue.proposed_dir / "0090-copyleft-integration.md"
    task = Task(
        id="0090",
        title="Copyleft Integration",
        status="Proposed",
        target_bc="security",
        allows_dependencies=True,
        file_path=task_file,
    )
    write_task_file(task)
    bdd_sec_ctx["task"] = task


@then('"spec-ops audit dependencies" flags the license violation')
def assert_audit_flags_license(bdd_sec_ctx: dict[str, Any]):
    repo: Path = bdd_sec_ctx["repo"]
    cmd = [sys.executable, "-m", "spec_ops.cli.main", "audit", "dependencies", "--path", str(repo)]
    res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, env=CLI_ENV)
    bdd_sec_ctx["cli_res"] = res
    assert res.returncode == 1, f"Expected returncode 1, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"
    out = (res.stdout + res.stderr).lower()
    assert "copyleft-lib" in out
    assert "agpl-3.0" in out


@then('"spec-ops audit dependencies" flags the non-compliant license violation')
def assert_audit_flags_non_compliant_license(bdd_sec_ctx: dict[str, Any]):
    assert_audit_flags_license(bdd_sec_ctx)


@then('blocks the task transition to "refined/" or "complete/" until replaced or approved with an explicit policy waiver.')
def assert_blocks_transitions(bdd_sec_ctx: dict[str, Any]):
    queue: BacklogQueue = bdd_sec_ctx["queue"]
    task: Task = bdd_sec_ctx["task"]
    repo: Path = bdd_sec_ctx["repo"]

    # Attempt transition to refined/ via gate
    ok_refine, msg_refine = queue.refine_task_with_gate(task, repo_root=repo)
    assert not ok_refine, f"Expected refinement gate to fail, but succeeded with: {msg_refine}"
    assert "non-compliant license" in msg_refine.lower() or "audit failed" in msg_refine.lower()

    # Attempt transition to complete/ via gate
    ok_comp, msg_comp = queue.complete_task_with_gate(task, repo_root=repo)
    assert not ok_comp, f"Expected completion gate to fail, but succeeded with: {msg_comp}"


# ==============================================================================
# Scenario: Evaluating approved license and CVE policy waivers
# ==============================================================================


@given('an active dependency with a restricted license has a valid waiver file in "docs/project/compliance/waivers/WAIVER-001.md" signed by Sasha and unexpired')
def setup_active_waiver_for_restricted_license(bdd_sec_ctx: dict[str, Any]):
    repo: Path = bdd_sec_ctx["repo"]

    # Ensure config restricts licenses
    config_file = repo / "specops.toml"
    current = config_file.read_text(encoding="utf-8") if config_file.exists() else ""
    if "[security.licenses]" not in current:
        config_file.write_text(current + '\n[security.licenses]\nallowed = ["MIT", "Apache-2.0", "BSD-3-Clause"]\n', encoding="utf-8")

    # Add restricted dependency
    lock_file = repo / "uv.lock"
    content = (
        'version = 1\nrevision = 1\nrequires-python = ">=3.13"\n\n'
        '[[package]]\nname = "copyleft-lib"\nversion = "2.0.0"\n'
        'license = "AGPL-3.0"\n'
        'source = { registry = "https://pypi.org/simple" }\n'
    )
    lock_file.write_text(content, encoding="utf-8")

    # Create valid signed unexpired waiver file
    waiver_dir = repo / "docs" / "project" / "compliance" / "waivers"
    waiver_dir.mkdir(parents=True, exist_ok=True)
    waiver_file = waiver_dir / "WAIVER-001.md"

    w_id = "WAIVER-001"
    pkg = "copyleft-lib"
    signer = "Sasha"
    expires = "2029-01-01"
    sig = compute_waiver_signature(w_id, pkg, signer, expires)

    waiver_text = (
        f"---\n"
        f"id: {w_id}\n"
        f"package: {pkg}\n"
        f"license: AGPL-3.0\n"
        f"signer: {signer}\n"
        f"expires: {expires}\n"
        f"signature: {sig}\n"
        f"status: Approved\n"
        f"reason: Temporary audited exception for internal analysis CLI tool\n"
        f"---\n\n"
        f"# Policy Waiver {w_id}\n\n"
        f"Signed by {signer} on 2026-09-29.\n"
    )
    waiver_file.write_text(waiver_text, encoding="utf-8")


@when('"spec-ops audit dependencies" executes')
def execute_audit_dependencies(bdd_sec_ctx: dict[str, Any]):
    repo: Path = bdd_sec_ctx["repo"]
    cmd = [sys.executable, "-m", "spec_ops.cli.main", "audit", "dependencies", "--path", str(repo)]
    res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, env=CLI_ENV)
    bdd_sec_ctx["cli_res"] = res


@then("the scanner logs the active waiver identifier and expiration date")
def assert_scanner_logs_waiver(bdd_sec_ctx: dict[str, Any]):
    res = bdd_sec_ctx["cli_res"]
    out = res.stdout + res.stderr
    assert "WAIVER-001" in out, f"Expected waiver ID in output. Output:\n{out}"
    assert "2029-01-01" in out, f"Expected expiration date in output. Output:\n{out}"


@then("allows the verification check to exit with returncode 0.")
def assert_exit_code_0(bdd_sec_ctx: dict[str, Any]):
    res = bdd_sec_ctx["cli_res"]
    assert res is not None, "CLI command did not run"
    assert res.returncode == 0, f"Expected returncode 0, got {res.returncode}. Output:\n{res.stdout}\n{res.stderr}"
