"""Executable BDD scenarios using pytest-bdd for SpecOps security profile story (US-0108)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
CLI_ENV = {**os.environ, "PYTHONPATH": f"{SRC_DIR}:{os.environ.get('PYTHONPATH', '')}".rstrip(":")}

scenarios("features/us_0108_security_guardrails.feature")


@pytest.fixture
def bdd_sec_context(tmp_path: Path) -> dict[str, Any]:
    """Shared state container for security BDD scenarios."""
    return {"dir": tmp_path, "res": None}


@given('a blank or existing project directory for "SecureEnterpriseApp"')
def blank_enterprise_dir(bdd_sec_context: dict[str, Any]):
    assert bdd_sec_context["dir"].is_dir()


@when('the security officer executes "spec-ops init --name SecureEnterpriseApp --profile core,bdd,ddd,security"')
def execute_init_secure_enterprise_app(bdd_sec_context: dict[str, Any]):
    target = bdd_sec_context["dir"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "init",
            "--name",
            "SecureEnterpriseApp",
            "--dir",
            str(target),
            "--profile",
            "core,bdd,ddd,security",
        ],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_sec_context["res"] = res


@then('"docs/project/adrs/accepted/" includes baseline security ADRs for process sandboxing, lockfile immutability, and credential leak defense')
def verify_security_adrs_us0108(bdd_sec_context: dict[str, Any]):
    root = bdd_sec_context["dir"]
    adrs_dir = root / "docs" / "project" / "adrs" / "accepted"
    adr_files = list(adrs_dir.glob("*.md"))
    names = [p.name for p in adr_files]
    assert any("zero-trust-worker-process-sandboxing" in name for name in names)
    assert any("immutable-supply-chain-lockfile-enforcement" in name for name in names)
    assert any("secret-scanning-and-credential-leak-defense" in name for name in names)


@then('"docs/project/SECURITY.md" is scaffolded with vulnerability disclosure workflows, PGP key fingerprints, and incident reporting contacts')
def verify_security_md_scaffolded_us0108(bdd_sec_context: dict[str, Any]):
    root = bdd_sec_context["dir"]
    sec_md = root / "docs" / "project" / "SECURITY.md"
    assert sec_md.is_file()
    content = sec_md.read_text(encoding="utf-8")
    assert "Vulnerability Disclosure" in content
    assert "Reporting Contacts" in content
    assert "PGP" in content
    assert "Fingerprint" in content


@then('"specops.toml" is generated containing an active "[security]" configuration block enabling secret scanning and lockfile immutability')
def verify_specops_toml_security_us0108(bdd_sec_context: dict[str, Any]):
    root = bdd_sec_context["dir"]
    toml_path = root / "specops.toml"
    assert toml_path.is_file()
    content = toml_path.read_text(encoding="utf-8")
    assert "[security]" in content
    assert "secret_scanning = true" in content
    assert "lockfile_immutability = true" in content


@then("the command exits with returncode 0")
@then("the command exits with returncode 0.")
def verify_exit_zero_nodot(bdd_sec_context: dict[str, Any]):
    assert bdd_sec_context["res"].returncode == 0


@given("a project configured with the security architectural profile")
def project_with_security_arch_profile(bdd_sec_context: dict[str, Any]):
    target = bdd_sec_context["dir"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "init",
            "--name",
            "EnterpriseSecured",
            "--dir",
            str(target),
            "--profile",
            "core,bdd,ddd,security",
        ],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 0


@when('the developer or orchestrator executes "spec-ops scaffold agents"')
def orchestrator_executes_scaffold_agents(bdd_sec_context: dict[str, Any]):
    target = bdd_sec_context["dir"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "scaffold", "agents"],
        cwd=str(target),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_sec_context["res"] = res
    assert res.returncode == 0


@then('the generated "AGENTS.md" at the repository root contains a "Security & Supply-Chain Hard Invariants" section')
def verify_agents_md_contains_hard_invariants(bdd_sec_context: dict[str, Any]):
    root = bdd_sec_context["dir"]
    agents_md = root / "AGENTS.md"
    assert agents_md.is_file()
    content = agents_md.read_text(encoding="utf-8")
    assert "Security & Supply-Chain Hard Invariants" in content


@then("the constitution explicitly forbids agents from hardcoding credentials, modifying unapproved lockfiles, or executing non-allowlisted shell commands")
def verify_forbids_credentials_lockfiles_commands_nodot(bdd_sec_context: dict[str, Any]):
    root = bdd_sec_context["dir"]
    content = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert "hardcoding credentials" in content
    assert "unapproved lockfiles" in content
    assert "non-allowlisted shell commands" in content


@then('running "spec-ops health" reports 0 file limit violations (<500 lines) and 0 constitution drift warnings.')
def verify_health_reports_zero_violations_and_drift(bdd_sec_context: dict[str, Any]):
    target = bdd_sec_context["dir"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "health"],
        cwd=str(target),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 0
    assert "0 file limit violations (<500 lines) and 0 constitution drift warnings" in res.stdout


@given('a repository configured with the security profile where "docs/project/SECURITY.md" was removed or modified out-of-spec')
def repo_with_removed_security_md(bdd_sec_context: dict[str, Any]):
    target = bdd_sec_context["dir"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "init",
            "--name",
            "DegradedSecured",
            "--dir",
            str(target),
            "--profile",
            "core,bdd,security",
        ],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 0
    sec_md = target / "docs" / "project" / "SECURITY.md"
    if sec_md.exists():
        sec_md.unlink()


@when('"spec-ops health --security" executes')
def execute_health_security(bdd_sec_context: dict[str, Any]):
    target = bdd_sec_context["dir"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "health", "--security"],
        cwd=str(target),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_sec_context["res"] = res


@then("the command exits with returncode 1")
def verify_exit_one_nodot(bdd_sec_context: dict[str, Any]):
    assert bdd_sec_context["res"].returncode == 1


@then('reports "Security Policy Invariant Violated: docs/project/SECURITY.md is missing or invalid. Run \'spec-ops profile sync security\' to restore".')
def verify_security_policy_invariant_violation_msg(bdd_sec_context: dict[str, Any]):
    stdout = bdd_sec_context["res"].stdout
    assert "Security Policy Invariant Violated: docs/project/SECURITY.md is missing or invalid. Run 'spec-ops profile sync security' to restore" in stdout


@given('a repository configured with the security profile having an active worktree missing "docs/project/SECURITY.md"')
def repo_with_active_worktree_missing_security_md(bdd_sec_context: dict[str, Any]):
    target = bdd_sec_context["dir"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "init",
            "--name",
            "WorktreeSecured",
            "--dir",
            str(target),
            "--profile",
            "core,bdd,security",
        ],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 0
    # Create active worktree directory under .worktrees/task-0099
    wt_dir = target / ".worktrees" / "task-0099"
    wt_dir.mkdir(parents=True, exist_ok=True)
    (wt_dir / ".git").write_text("gitdir: /fake/dir", encoding="utf-8")
    shutil.copy2(target / "specops.toml", wt_dir / "specops.toml")
    # Simulate root having missing SECURITY.md
    sec_md = target / "docs" / "project" / "SECURITY.md"
    if sec_md.exists():
        sec_md.unlink()
    bdd_sec_context["wt_dir"] = wt_dir


@when('the developer executes "spec-ops profile sync security"')
def developer_executes_profile_sync_security(bdd_sec_context: dict[str, Any]):
    target = bdd_sec_context["dir"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "profiles", "sync", "security"],
        cwd=str(target),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_sec_context["res"] = res
    assert res.returncode == 0


@then('"docs/project/SECURITY.md" is restored in both the root repository and the active worktree')
def verify_security_md_restored_in_root_and_worktree(bdd_sec_context: dict[str, Any]):
    target = bdd_sec_context["dir"]
    wt_dir = bdd_sec_context["wt_dir"]
    assert (target / "docs" / "project" / "SECURITY.md").is_file()
    assert (wt_dir / "docs" / "project" / "SECURITY.md").is_file()


@then('executing "spec-ops health --security" in the worktree succeeds with returncode 0')
def verify_health_security_in_worktree_succeeds(bdd_sec_context: dict[str, Any]):
    wt_dir = bdd_sec_context["wt_dir"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "health", "--security"],
        cwd=str(wt_dir),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 0
    assert "Security policies and guardrails verified" in res.stdout
