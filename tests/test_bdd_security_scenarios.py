"""Executable BDD scenarios using pytest-bdd for SpecOps security profile stories (US-0051, US-0108)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
CLI_ENV = {**os.environ, "PYTHONPATH": f"{SRC_DIR}:{os.environ.get('PYTHONPATH', '')}".rstrip(":")}

scenarios("features/us_0051_security_profile.feature")


@pytest.fixture
def bdd_sec_context(tmp_path: Path) -> dict[str, Any]:
    """Shared state container for security BDD scenarios."""
    return {"dir": tmp_path, "res": None}


# --- US-0051 Steps ---


@given("a blank or existing project directory")
def blank_or_existing_project_directory(bdd_sec_context: dict[str, Any]):
    assert bdd_sec_context["dir"].is_dir()


@when('the security officer executes "spec-ops init --name SecureApp --profile core,bdd,security"')
def execute_init_secure_app(bdd_sec_context: dict[str, Any]):
    target = bdd_sec_context["dir"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "init",
            "--name",
            "SecureApp",
            "--dir",
            str(target),
            "--profile",
            "core,bdd,security",
        ],
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_sec_context["res"] = res


@then('"docs/project/adrs/accepted/" includes baseline security ADRs for zero-trust agent sandboxing and supply-chain immutability')
def verify_security_adrs_us0051(bdd_sec_context: dict[str, Any]):
    root = bdd_sec_context["dir"]
    adrs_dir = root / "docs" / "project" / "adrs" / "accepted"
    adr_files = list(adrs_dir.glob("*.md"))
    names = [p.name for p in adr_files]
    assert any("zero-trust-worker-process-sandboxing" in name for name in names)
    assert any("immutable-supply-chain-lockfile-enforcement" in name for name in names)


@then('"docs/project/SECURITY.md" is scaffolded with vulnerability disclosure workflows and reporting contacts')
def verify_security_md_scaffolded_us0051(bdd_sec_context: dict[str, Any]):
    root = bdd_sec_context["dir"]
    sec_md = root / "docs" / "project" / "SECURITY.md"
    assert sec_md.is_file()
    content = sec_md.read_text(encoding="utf-8")
    assert "Vulnerability Disclosure" in content
    assert "Reporting Contacts" in content


@then('"specops.toml" is generated with a "[security]" configuration block enabling secret scanning and lockfile enforcement')
def verify_specops_toml_security_us0051(bdd_sec_context: dict[str, Any]):
    root = bdd_sec_context["dir"]
    toml_path = root / "specops.toml"
    assert toml_path.is_file()
    content = toml_path.read_text(encoding="utf-8")
    assert "[security]" in content
    assert "secret_scanning = true" in content
    assert "enforce_lockfile = true" in content


@then("the command exits with returncode 0.")
def verify_exit_zero_dot(bdd_sec_context: dict[str, Any]):
    assert bdd_sec_context["res"].returncode == 0


@given("a project configured with the security profile")
def project_with_security_profile(bdd_sec_context: dict[str, Any]):
    target = bdd_sec_context["dir"]
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "spec_ops.cli.main",
            "init",
            "--name",
            "SecuredRepo",
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


@when('the developer executes "spec-ops scaffold agents"')
def developer_executes_scaffold_agents(bdd_sec_context: dict[str, Any]):
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


@then('the generated "AGENTS.md" at the repository root contains a "Security & Supply-Chain Invariants" section')
def verify_agents_md_contains_invariants_us0051(bdd_sec_context: dict[str, Any]):
    root = bdd_sec_context["dir"]
    agents_md = root / "AGENTS.md"
    assert agents_md.is_file()
    content = agents_md.read_text(encoding="utf-8")
    assert "Security & Supply-Chain" in content
    assert "Invariants" in content


@then("the constitution explicitly forbids agents from hardcoding credentials, modifying unapproved lockfiles, or executing non-allowlisted shell commands.")
def verify_forbids_credentials_lockfiles_commands_dot(bdd_sec_context: dict[str, Any]):
    root = bdd_sec_context["dir"]
    content = (root / "AGENTS.md").read_text(encoding="utf-8")
    assert "hardcoding credentials" in content
    assert "unapproved lockfiles" in content
    assert "non-allowlisted shell commands" in content


