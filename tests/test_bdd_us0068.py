"""Executable BDD scenarios for US-0068: Living Constitution Synchronization, Extension Preservation, and CI Drift Gate."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0068_living_constitution_synchronization_and_ci_drift_gate.feature")


@pytest.fixture
def bdd_us68_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="ConstitutionSyncApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Morgan"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "morgan@specops.dev"], cwd=repo, check=True, capture_output=True)

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial scaffold"], cwd=repo, check=True, capture_output=True)

    return {
        "repo": repo,
        "last_cmd": None,
        "last_res": None,
        "initial_agents_content": None,
    }


# ============================================================================
# Scenario: Re-synchronizing constitution when specops.toml settings change
# ============================================================================


@given('an existing project where "specops.toml" has updated "file_length_limit = 350" and added a new quality preflight command "ruff check"')
def project_with_updated_settings(bdd_us68_context: dict[str, Any]):
    repo: Path = bdd_us68_context["repo"]
    toml_path = repo / "specops.toml"
    content = toml_path.read_text(encoding="utf-8")

    # Update file_length_limit
    content = re.sub(r"file_length_limit\s*=\s*\d+", "file_length_limit = 350", content)

    # Add quality preflight command "ruff check"
    if "preflight =" in content:
        content = re.sub(
            r'preflight\s*=\s*\[(.*?)\]',
            'preflight = ["pytest", "ruff check"]',
            content,
            flags=re.DOTALL,
        )
    else:
        content += '\n[quality]\npreflight = ["pytest", "ruff check"]\n'

    toml_path.write_text(content, encoding="utf-8")
    bdd_us68_context["initial_agents_content"] = (repo / "AGENTS.md").read_text(encoding="utf-8")


@when('the developer or agent runs "spec-ops scaffold agents" (or "spec-ops constitution sync")')
def run_scaffold_agents_or_sync(bdd_us68_context: dict[str, Any]):
    repo: Path = bdd_us68_context["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "constitution", "sync"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    bdd_us68_context["last_res"] = res


@then('"AGENTS.md" is regenerated with the updated 350-line limit and new preflight command in the Hard Invariants and Task Workflow sections')
def verify_agents_md_regenerated(bdd_us68_context: dict[str, Any]):
    repo: Path = bdd_us68_context["repo"]
    agents_path = repo / "AGENTS.md"
    assert agents_path.is_file()
    content = agents_path.read_text(encoding="utf-8")

    # Verify updated 350-line limit in Hard Invariants
    assert "File Length Limit (<350 lines)" in content
    assert "Source files over ~350 lines" in content
    assert "warns proactively at >=250 lines" in content

    # Verify new preflight command "ruff check" in Hard Invariants
    invariants_part = content.split("## Hard Invariants")[1].split("## ")[0]
    assert "ruff check" in invariants_part

    # Verify new preflight command in Task Execution Workflow
    workflow_part = content.split("## Task Execution Workflow")[1]
    assert "ruff check" in workflow_part


@then('"docs/operating-manual.md" is updated synchronously with adjusted relative documentation links')
def verify_operating_manual_updated(bdd_us68_context: dict[str, Any]):
    repo: Path = bdd_us68_context["repo"]
    manual_path = repo / "docs" / "operating-manual.md"
    assert manual_path.is_file()
    content = manual_path.read_text(encoding="utf-8")

    assert "File Length Limit (<350 lines)" in content
    assert "ruff check" in content
    # Verify no raw root docs/ links
    assert "](docs/" not in content


@then("all unchanged sections remain structurally intact.")
def verify_unchanged_sections_intact(bdd_us68_context: dict[str, Any]):
    repo: Path = bdd_us68_context["repo"]
    content = (repo / "AGENTS.md").read_text(encoding="utf-8")

    assert "## Design Principles" in content
    assert "## Project Structure & Navigation" in content
    assert "## Definition of Ready (DoR)" in content
    assert "## Definition of Done (DoD)" in content
    assert "Blackbox Frontdoor Verification" in content
    assert "Strict Backlog Isolation" in content


# ============================================================================
# Scenario: Preserving human-authored custom invariant extensions across sync
# ============================================================================


@given('an "AGENTS.md" containing a marked user section "<!-- BEGIN CUSTOM INVARIANTS -->" with team-specific guidelines "Always run local emulator on port 9090"')
def agents_md_with_custom_invariants(bdd_us68_context: dict[str, Any]):
    repo: Path = bdd_us68_context["repo"]
    agents_path = repo / "AGENTS.md"
    content = agents_path.read_text(encoding="utf-8")

    custom_block = (
        "<!-- BEGIN CUSTOM INVARIANTS -->\n"
        "Always run local emulator on port 9090\n"
        "<!-- END CUSTOM INVARIANTS -->"
    )

    if "<!-- BEGIN CUSTOM INVARIANTS -->" in content:
        content = re.sub(
            r"<!-- BEGIN CUSTOM INVARIANTS -->.*?<!-- END CUSTOM INVARIANTS -->",
            custom_block,
            content,
            flags=re.DOTALL,
        )
    else:
        marker = "## Design Principles"
        parts = content.split(marker, 1)
        content = f"{parts[0]}\n{custom_block}\n\n---\n\n{marker}{parts[1]}"

    agents_path.write_text(content, encoding="utf-8")
    bdd_us68_context["custom_guideline"] = "Always run local emulator on port 9090"


@when('"spec-ops scaffold agents" is executed after profile updates')
def execute_scaffold_agents(bdd_us68_context: dict[str, Any]):
    repo: Path = bdd_us68_context["repo"]
    # Change setting in specops.toml
    toml_path = repo / "specops.toml"
    text = toml_path.read_text(encoding="utf-8")
    text = re.sub(r"file_length_limit\s*=\s*\d+", "file_length_limit = 420", text)
    toml_path.write_text(text, encoding="utf-8")

    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "scaffold", "agents"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0
    bdd_us68_context["last_res"] = res


@then("the regenerated \"AGENTS.md\" retains the exact contents within the custom invariants block")
def verify_custom_invariants_preserved(bdd_us68_context: dict[str, Any]):
    repo: Path = bdd_us68_context["repo"]
    content = (repo / "AGENTS.md").read_text(encoding="utf-8")

    assert "<!-- BEGIN CUSTOM INVARIANTS -->" in content
    assert "<!-- END CUSTOM INVARIANTS -->" in content
    assert bdd_us68_context["custom_guideline"] in content


@then("updates the profile-driven sections around it without data loss.")
def verify_profile_sections_updated(bdd_us68_context: dict[str, Any]):
    repo: Path = bdd_us68_context["repo"]
    content = (repo / "AGENTS.md").read_text(encoding="utf-8")

    assert "File Length Limit (<420 lines)" in content
    assert "## Design Principles" in content
    assert "## Task Execution Workflow" in content


# ============================================================================
# Scenario: CI constitution drift detection gate
# ============================================================================


@given('a pull request where "specops.toml" architectural settings were modified without re-running constitution sync')
def modified_settings_without_sync(bdd_us68_context: dict[str, Any]):
    repo: Path = bdd_us68_context["repo"]
    # Ensure constitution was synced first
    res_sync = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "constitution", "sync"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    assert res_sync.returncode == 0

    # Modify architectural settings without running sync
    toml_path = repo / "specops.toml"
    text = toml_path.read_text(encoding="utf-8")
    text = re.sub(r"file_length_limit\s*=\s*\d+", "file_length_limit = 300", text)
    toml_path.write_text(text, encoding="utf-8")


@when('"spec-ops constitution check" runs during CI preflight')
def run_constitution_check(bdd_us68_context: dict[str, Any]):
    repo: Path = bdd_us68_context["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "constitution", "check"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    bdd_us68_context["last_res"] = res


@then('the command detects a mismatch between "specops.toml" and root "AGENTS.md"')
def verify_mismatch_detected(bdd_us68_context: dict[str, Any]):
    res = bdd_us68_context["last_res"]
    assert res is not None
    # Check that diff diagnostics were printed
    assert "AGENTS.md (actual)" in res.stdout or "AGENTS.md" in res.stdout


@then("exits with code 1")
def verify_exit_code_1(bdd_us68_context: dict[str, Any]):
    res = bdd_us68_context["last_res"]
    assert res.returncode == 1


@then('outputs "Constitution Drift Error: AGENTS.md is out of sync with specops.toml. Run \'spec-ops scaffold agents\' to update."')
def verify_error_output(bdd_us68_context: dict[str, Any]):
    res = bdd_us68_context["last_res"]
    expected_msg = "Constitution Drift Error: AGENTS.md is out of sync with specops.toml. Run 'spec-ops scaffold agents' to update."
    assert expected_msg in res.stdout
