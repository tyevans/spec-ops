"""Executable BDD scenarios for US-0014: ADR Supersession and Constitution Synchronization."""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.core.parser import extract_frontmatter
from spec_ops.scaffold.init import init_project

scenarios("features/us_0014_adr_supersession_and_living_constitution_sync.feature")


@pytest.fixture
def adr_context(tmp_path: Path) -> dict[str, Any]:
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(name="ADRSyncApp", target_dir=repo)

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Alex"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "alex@specops.dev"], cwd=repo, check=True, capture_output=True)

    # Initial commit so git history is clean
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True, capture_output=True)

    return {
        "repo": repo,
        "last_cmd": None,
        "last_res": None,
        "health_res": None,
    }


# ============================================================================
# Scenario: Superseding an ADR and updating registry links
# ============================================================================


@given(parsers.parse('an accepted ADR "{adr_title}"'))
def setup_accepted_adr(adr_context: dict[str, Any], adr_title: str):
    repo: Path = adr_context["repo"]
    adrs_accepted = repo / "docs" / "project" / "adrs" / "accepted"
    adrs_accepted.mkdir(parents=True, exist_ok=True)

    # e.g. "ADR-0003: Blackbox Frontdoor Verification"
    file_path = adrs_accepted / "adr-0003-blackbox-frontdoor-verification.md"
    content = (
        "---\n"
        "id: '0003'\n"
        "title: Blackbox Frontdoor Verification and Zero Backdoor Testing\n"
        "status: Accepted\n"
        "---\n\n"
        "# ADR-0003: Blackbox Frontdoor Verification and Zero Backdoor Testing\n\n"
        "## Status\n"
        "Accepted\n\n"
        "## Context\n"
        "Tests must verify public contracts.\n"
    )
    file_path.write_text(content, encoding="utf-8")

    # Update REGISTRY.md
    registry = repo / "docs" / "project" / "adrs" / "REGISTRY.md"
    reg_text = (
        "# ADR Registry\n\n"
        "| ID | Title | Status | Date |\n"
        "|---|---|---|---|\n"
        "| ADR-0001 | Specification as Code | Accepted | 2026-09-29 |\n"
        "| ADR-0002 | Modular File Limit | Accepted | 2026-09-29 |\n"
        "| ADR-0003 | Blackbox Frontdoor Verification | Accepted | 2026-09-29 |\n"
    )
    registry.write_text(reg_text, encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "docs: setup accepted ADR-0003"], cwd=repo, check=True, capture_output=True)


@given(parsers.parse('a newly drafted ADR "{rel_path}"'))
def setup_proposed_adr(adr_context: dict[str, Any], rel_path: str):
    repo: Path = adr_context["repo"]
    full_path = repo / rel_path
    full_path.parent.mkdir(parents=True, exist_ok=True)

    content = (
        "---\n"
        "id: '0015'\n"
        "title: Enhanced Frontdoor Contracts\n"
        "status: Proposed\n"
        "---\n\n"
        "# ADR-0015: Enhanced Frontdoor Contracts\n\n"
        "## Status\n"
        "Proposed\n\n"
        "## Context\n"
        "Enhanced contracts provide schema verification.\n"
    )
    full_path.write_text(content, encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "docs: draft ADR-0015"], cwd=repo, check=True, capture_output=True)


@when(parsers.parse('the architect runs "{command}"'))
def run_architect_command(adr_context: dict[str, Any], command: str):
    repo: Path = adr_context["repo"]
    parts = shlex.split(command)
    if parts and parts[0] == "spec-ops":
        cmd = [sys.executable, "-m", "spec_ops.cli.main", *parts[1:]]
    else:
        cmd = parts

    res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    adr_context["last_cmd"] = command
    adr_context["last_res"] = res


@then(parsers.parse('"{adr_id}" status is updated to "{status}" with frontmatter "{frontmatter_key}: {frontmatter_val}"'))
def verify_adr_frontmatter(adr_context: dict[str, Any], adr_id: str, status: str, frontmatter_key: str, frontmatter_val: str):
    repo: Path = adr_context["repo"]
    adrs_dir = repo / "docs" / "project" / "adrs"

    # Find the ADR file for adr_id
    matching_files = [
        p for p in adrs_dir.rglob("*.md")
        if adr_id.lower() in p.stem.lower() and p.name not in ("REGISTRY.md", "README.md")
    ]
    assert matching_files, f"Could not find ADR file for {adr_id}"
    adr_file = matching_files[0]

    meta, body = extract_frontmatter(adr_file.read_text(encoding="utf-8"))
    assert meta.get("status") == status, f"Expected status {status}, got {meta.get('status')}"
    assert meta.get(frontmatter_key) == frontmatter_val, f"Expected {frontmatter_key}={frontmatter_val}, got {meta.get(frontmatter_key)}"


@then(parsers.parse('"{adr_id}" is moved to "{dest_folder}" with status "{status}"'))
def verify_adr_moved(adr_context: dict[str, Any], adr_id: str, dest_folder: str, status: str):
    repo: Path = adr_context["repo"]
    target_dir = repo / dest_folder
    assert target_dir.exists(), f"Destination folder {dest_folder} does not exist"

    matching_files = [
        p for p in target_dir.glob("*.md")
        if adr_id.lower() in p.stem.lower() and p.name not in ("REGISTRY.md", "README.md")
    ]
    assert matching_files, f"Expected {adr_id} in {dest_folder}, but found none"
    meta, _ = extract_frontmatter(matching_files[0].read_text(encoding="utf-8"))
    assert meta.get("status") == status


@then(parsers.parse('"{registry_path}" is updated to reflect the supersession link.'))
def verify_registry_link(adr_context: dict[str, Any], registry_path: str):
    repo: Path = adr_context["repo"]
    reg_file = repo / registry_path
    assert reg_file.exists(), f"Registry file {registry_path} does not exist"

    content = reg_file.read_text(encoding="utf-8")
    assert "ADR-0003" in content
    assert "Superseded (by ADR-0015)" in content
    assert "ADR-0015" in content
    assert "Accepted" in content


# ============================================================================
# Scenario: Re-synchronizing AGENTS.md constitution upon ADR supersession
# ============================================================================


@given("ADR-0003 has been superseded by ADR-0015")
def given_adr_superseded(adr_context: dict[str, Any]):
    setup_accepted_adr(adr_context, "ADR-0003: Blackbox Frontdoor Verification")
    setup_proposed_adr(adr_context, "docs/project/adrs/proposed/adr-0015-enhanced-frontdoor-contracts.md")
    run_architect_command(
        adr_context,
        "spec-ops adr supersede ADR-0003 --with docs/project/adrs/proposed/adr-0015-enhanced-frontdoor-contracts.md",
    )
    assert adr_context["last_res"].returncode == 0


@when('the system updates the agent constitution via "spec-ops scaffold agents"')
def run_scaffold_agents(adr_context: dict[str, Any]):
    repo: Path = adr_context["repo"]
    cmd = [sys.executable, "-m", "spec_ops.cli.main", "scaffold", "agents"]
    res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    assert res.returncode == 0, f"spec-ops scaffold agents failed: {res.stderr}"
    adr_context["last_res"] = res


@then('the Hard Invariants section in "AGENTS.md" replaces the rules of ADR-0003 with the rules of ADR-0015')
def verify_agents_md_replaced(adr_context: dict[str, Any]):
    repo: Path = adr_context["repo"]
    agents_md = repo / "AGENTS.md"
    assert agents_md.exists()

    content = agents_md.read_text(encoding="utf-8")
    assert "## Hard Invariants" in content

    # Find Hard Invariants section
    invariants_part = content.split("## Hard Invariants")[1].split("## ")[0]
    assert "ADR-0003" not in invariants_part
    assert "ADR-0015" in invariants_part


@then(parsers.parse('commits the change cleanly with trailer "{trailer}".'))
def verify_git_commit_trailer(adr_context: dict[str, Any], trailer: str):
    repo: Path = adr_context["repo"]
    log_res = subprocess.run(["git", "log", "-1", "--format=%B"], cwd=repo, capture_output=True, text=True, check=True)
    commit_msg = log_res.stdout
    assert trailer in commit_msg, f"Expected trailer '{trailer}' in commit message:\n{commit_msg}"


# ============================================================================
# Scenario: Flagging active backlog tasks citing superseded ADRs
# ============================================================================


@given(parsers.parse('task "{task_id}" in "{folder}" cites "{citation}"'))
def setup_task_citing_adr(adr_context: dict[str, Any], task_id: str, folder: str, citation: str):
    repo: Path = adr_context["repo"]
    setup_accepted_adr(adr_context, "ADR-0003: Blackbox Frontdoor Verification")
    setup_proposed_adr(adr_context, "docs/project/adrs/proposed/adr-0015-enhanced-frontdoor-contracts.md")

    target_dir = repo / folder
    target_dir.mkdir(parents=True, exist_ok=True)
    task_file = target_dir / "0014-active-task.md"

    # Citation e.g. "governing_adr: ADR-0003"
    content = (
        "---\n"
        f"id: '{task_id.replace('TASK-', '')}'\n"
        "title: Active Feature Task\n"
        "status: Refined\n"
        f"{citation}\n"
        "---\n\n"
        f"# {task_id}: Active Feature Task\n\n"
        "Scenario: Feature Execution\n"
        "Given system is active\n"
        "When command runs\n"
        "Then result is positive\n"
    )
    task_file.write_text(content, encoding="utf-8")

    # Update PRIORITY.md
    priority = repo / "docs" / "project" / "backlog" / "PRIORITY.md"
    priority.parent.mkdir(parents=True, exist_ok=True)
    p_text = (
        "# Priority Queue\n\n"
        f"1. **{task_id} (Refined)**: [`0014-active-task.md`](refined/0014-active-task.md)\n"
    )
    priority.write_text(p_text, encoding="utf-8")

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "docs: create task citing ADR-0003"], cwd=repo, check=True, capture_output=True)


@then(parsers.parse('"{task_id}" is flagged with a warning in "spec-ops health"'))
def verify_task_flagged_in_health(adr_context: dict[str, Any], task_id: str):
    repo: Path = adr_context["repo"]
    cmd = [sys.executable, "-m", "spec_ops.cli.main", "health"]
    res = subprocess.run(cmd, cwd=repo, capture_output=True, text=True)
    adr_context["health_res"] = res

    # The warning should be present in output
    assert task_id in res.stdout, f"Expected {task_id} in health output:\n{res.stdout}"
    assert "warning" in res.stdout.lower() or "⚠️" in res.stdout


@then(parsers.parse('reports "{report_msg}".'))
def verify_health_reports_message(adr_context: dict[str, Any], report_msg: str):
    health_res = adr_context.get("health_res")
    assert health_res is not None, "Health command was not executed"
    assert report_msg in health_res.stdout, f"Expected report message '{report_msg}' in output:\n{health_res.stdout}"
