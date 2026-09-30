"""Unit tests for shipping validation checks, roadmap/registry reconciliation, and release gates."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from spec_ops.config.loader import load_config
from spec_ops.core.parser import extract_frontmatter
from spec_ops.prd.shipping import (
    locate_prd_file,
    reconcile_shipping_uat_status,
    ship_prd,
    update_registry_shipped,
    update_roadmap_shipped,
    validate_shipping_tasks,
    validate_shipping_tests,
)
from spec_ops.scaffold.init import init_project


class MockTask:
    def __init__(self, canonical_id: str, status: str):
        self.canonical_id = canonical_id
        self.status = status


def test_validate_shipping_tasks_empty():
    ok, err = validate_shipping_tasks([], "PRD-0001")
    assert ok is False
    assert "No implementing tasks found" in err


def test_validate_shipping_tasks_incomplete():
    tasks = [
        MockTask("TASK-0001", "Complete"),
        MockTask("TASK-0002", "Refined"),
        MockTask("TASK-0003", "Proposed"),
    ]
    ok, err = validate_shipping_tasks(tasks, "PRD-0001")
    assert ok is False
    assert "Cannot ship PRD-0001: Incomplete tasks remaining (TASK-0002: Refined, TASK-0003: Proposed)" in err


def test_validate_shipping_tasks_all_complete():
    tasks = [
        MockTask("TASK-0001", "Complete"),
        MockTask("TASK-0002", "Complete"),
    ]
    ok, err = validate_shipping_tasks(tasks, "PRD-0001")
    assert ok is True
    assert err == ""


def test_validate_shipping_tests_invalid_type():
    ok, err = validate_shipping_tests([], None, "PRD-0001")  # type: ignore
    assert ok is False
    assert "Missing test verification summary" in err


def test_validate_shipping_tests_failing_status():
    ok, err = validate_shipping_tests([], {"status": "Failed (CI)", "failed_scenarios": 1}, "PRD-0001")
    assert ok is False
    assert "Linked BDD user stories or tests failed frontdoor verification (1 failed)" in err


def test_validate_shipping_tests_zero_failures_passed():
    ok, err = validate_shipping_tests([], {"status": "Passed (CI)", "failed_scenarios": 0}, "PRD-0001")
    assert ok is True
    assert err == ""


def test_reconcile_shipping_uat_status_variants():
    # Non-dict signoffs
    all_app, summ = reconcile_shipping_uat_status("PRD-0001", ["1", "2"], None)  # type: ignore
    assert all_app is False
    assert summ["status"] == "Pending PM"
    assert summ["approved_outcomes"] == 0

    # Partial
    data = {
        "signoffs": {
            "PRD-0001:1": {"status": "Approved"},
            "PRD-0001:2": {"status": "Pending PM"},
        }
    }
    all_app, summ = reconcile_shipping_uat_status("PRD-0001", ["1", "2"], data)
    assert all_app is False
    assert summ["approved_outcomes"] == 1
    assert summ["total_outcomes"] == 2

    # All approved
    data["signoffs"]["PRD-0001:2"]["status"] = "Approved"
    all_app, summ = reconcile_shipping_uat_status("PRD-0001", ["1", "2"], data)
    assert all_app is True
    assert summ["status"] == "Approved"
    assert summ["approved_outcomes"] == 2


def test_update_registry_shipped_creates_and_updates(tmp_path: Path):
    reg_path = tmp_path / "docs" / "project" / "product" / "REGISTRY.md"

    # Creates fresh registry if missing
    update_registry_shipped(reg_path, "PRD-0001", "Initial Engine", "Taylor", "core")
    content = reg_path.read_text(encoding="utf-8")
    assert "| `PRD-0001` | Initial Engine | Shipped | Taylor | core |" in content

    # Updates existing row
    update_registry_shipped(reg_path, "PRD-0001", "Updated Engine", "Taylor", "core")
    content2 = reg_path.read_text(encoding="utf-8")
    assert "| `PRD-0001` | Updated Engine | Shipped | Taylor | core |" in content2


def test_update_roadmap_shipped_marks_complete(tmp_path: Path):
    rm_path = tmp_path / "docs" / "project" / "backlog" / "ROADMAP.md"
    rm_path.parent.mkdir(parents=True, exist_ok=True)
    rm_path.write_text("# Roadmap\n\n## Milestone 1: Setup (Active)\n- Task 1\n", encoding="utf-8")

    update_roadmap_shipped(rm_path, "PRD-0001", "Core Engine", shipped_date="2026-09-29")
    content = rm_path.read_text(encoding="utf-8")
    assert "## Milestone 1: Setup (Complete with 100% delivery)" in content
    assert "- Milestone completion date: 2026-09-29 (Horizon closed for PRD-0001 — Core Engine — Complete with 100% delivery)." in content

    # Calling again does not duplicate completion entry
    update_roadmap_shipped(rm_path, "PRD-0001", "Core Engine", shipped_date="2026-09-29")
    content2 = rm_path.read_text(encoding="utf-8")
    assert content2.count("Horizon closed for PRD-0001") == 1


def test_locate_prd_file_resolution(tmp_path: Path):
    prd_dir = tmp_path / "docs" / "project" / "product"
    acc_dir = prd_dir / "accepted"
    acc_dir.mkdir(parents=True, exist_ok=True)
    f = acc_dir / "prd-0009-special.md"
    f.write_text("---\nid: '0009'\ntitle: Special\n---\n# Special", encoding="utf-8")

    # By file path
    assert locate_prd_file(prd_dir, f) == f.resolve()
    # By canonical ID
    assert locate_prd_file(prd_dir, "PRD-0009") == f.resolve()
    # By number
    assert locate_prd_file(prd_dir, "9") == f.resolve()
    # Nonexistent
    assert locate_prd_file(prd_dir, "PRD-9999") is None


def test_ship_prd_end_to_end(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    init_project(repo, name="ShipEndToEnd")

    import subprocess
    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Jordan"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "jordan@specops.dev"], cwd=repo, check=True, capture_output=True)

    prd_file = repo / "docs" / "project" / "product" / "accepted" / "prd-0001-engine.md"
    prd_file.parent.mkdir(parents=True, exist_ok=True)
    prd_file.write_text(
        "---\nid: '0001'\ntitle: Engine\nstatus: Accepted\ntarget_persona: Taylor\ncomponent: core\n---\n\n# PRD-0001\n\n## Checkable Outcomes\n1. Engine works\n\n## Implementing Backlog Tasks\n- `TASK-0001`\n",
        encoding="utf-8",
    )

    t_file = repo / "docs" / "project" / "backlog" / "complete" / "0001-task.md"
    t_file.parent.mkdir(parents=True, exist_ok=True)
    t_file.write_text(
        "---\nid: '0001'\ntitle: Engine Task\nstatus: Complete\ngoverning_prds:\n  - PRD-0001\n---\n# TASK-0001\n",
        encoding="utf-8",
    )

    subprocess.run(["git", "add", "-A"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], cwd=repo, check=True, capture_output=True)

    config = load_config(repo)
    ok, msg = ship_prd(config, "PRD-0001")
    assert ok is True
    assert "Successfully shipped PRD-0001" in msg

    # File moved
    shipped_file = repo / "docs" / "project" / "product" / "shipped" / "prd-0001-engine.md"
    assert shipped_file.is_file()
    assert not prd_file.exists()

    # Frontmatter updated
    meta, _ = extract_frontmatter(shipped_file.read_text(encoding="utf-8"))
    assert meta.get("status") == "Shipped"
    assert str(meta.get("shipped_date")) == date.today().isoformat()

    # Manifest generated
    manifest_file = repo / "dist" / "releases" / "PRD-0001-release-manifest.json"
    assert manifest_file.is_file()
    m_data = json.loads(manifest_file.read_text(encoding="utf-8"))
    assert m_data["prd"]["id"] == "PRD-0001"
    assert len(m_data["completed_tasks"]) == 1
    assert m_data["completed_tasks"][0]["id"] == "TASK-0001"
