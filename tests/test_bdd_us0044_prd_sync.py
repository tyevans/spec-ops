"""Executable BDD scenarios for US-0044 (PRD Sync & Auto-Save).

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009, ADR-0013; PRD-0003; US-0044.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

from spec_ops.visualizer.prd_sync import (
    PRDSyncEngine,
    compute_sha256,
    get_draft_status,
    save_draft,
)

scenarios("features/us_0044_prd_sync.feature")


@pytest.fixture
def bdd_sync_context(tmp_path: Path) -> dict[str, Any]:
    """Shared state container for PRD sync BDD scenarios."""
    idea_dir = tmp_path / "docs" / "project" / "product" / "idea"
    idea_dir.mkdir(parents=True, exist_ok=True)
    return {
        "repo_root": tmp_path,
        "engine": PRDSyncEngine(repo_root=tmp_path, debounce_interval=0.05),
        "prd_path": None,
        "base_hash": None,
        "save_result": None,
        "updated_content": None,
        "client_draft": None,
    }


# Scenario 1: Debounced auto-save of visual PRD modifications


@given("an active editing session in Web PRD Studio")
def active_editing_session(bdd_sync_context: dict[str, Any]):
    repo_root: Path = bdd_sync_context["repo_root"]
    prd_file = repo_root / "docs" / "project" / "product" / "idea" / "prd-0001-customer-portal.md"
    initial_content = (
        "---\n"
        "id: PRD-0001\n"
        "title: Customer Portal\n"
        "status: Idea\n"
        "target_persona: Taylor\n"
        "component: core\n"
        "---\n\n"
        "# PRD-0001: Customer Portal\n\n"
        "## Problem Statement\n"
        "Initial problem description.\n\n"
        "## Checkable Outcomes\n"
        "- Initial outcome 1\n"
    )
    prd_file.write_text(initial_content, encoding="utf-8")
    bdd_sync_context["prd_path"] = prd_file
    bdd_sync_context["base_hash"] = compute_sha256(initial_content)


@when("the user edits checkable outcomes and pauses typing")
def user_edits_checkable_outcomes(bdd_sync_context: dict[str, Any]):
    prd_file: Path = bdd_sync_context["prd_path"]
    engine: PRDSyncEngine = bdd_sync_context["engine"]
    base_hash: str = bdd_sync_context["base_hash"]

    updated_content = (
        "---\n"
        "id: PRD-0001\n"
        "title: Customer Portal\n"
        "status: Idea\n"
        "target_persona: Taylor\n"
        "component: core\n"
        "---\n\n"
        "# PRD-0001: Customer Portal\n\n"
        "## Problem Statement\n"
        "Initial problem description.\n\n"
        "## Checkable Outcomes\n"
        "- Initial outcome 1\n"
        "- User updates payment method via UI\n"
        "- Webhook returns 200 OK confirmation\n"
    )
    bdd_sync_context["updated_content"] = updated_content

    # User types with debouncing, then pauses typing (flush pending)
    engine.debounce_save(prd_file, updated_content, expected_hash=base_hash)
    results = engine.flush_pending(prd_file)
    assert len(results) == 1
    bdd_sync_context["save_result"] = results[0]


@then('the draft changes are auto-saved to disk in "docs/project/product/"')
def draft_changes_autosaved_to_disk(bdd_sync_context: dict[str, Any]):
    prd_file: Path = bdd_sync_context["prd_path"]
    assert prd_file.exists()
    disk_content = prd_file.read_text(encoding="utf-8")
    assert "- User updates payment method via UI" in disk_content
    assert "- Webhook returns 200 OK confirmation" in disk_content


@then("the server returns a confirmed revision digest")
def server_returns_confirmed_revision_digest(bdd_sync_context: dict[str, Any]):
    res = bdd_sync_context["save_result"]
    prd_file: Path = bdd_sync_context["prd_path"]
    expected_digest = compute_sha256(prd_file.read_text(encoding="utf-8"))

    assert res.status == "saved"
    assert res.revision_digest == expected_digest
    assert len(res.revision_digest) == 64


# Scenario 2: Detecting concurrent external modifications


@given("an open PRD draft in the browser")
def open_prd_draft_in_browser(bdd_sync_context: dict[str, Any]):
    repo_root: Path = bdd_sync_context["repo_root"]
    prd_file = repo_root / "docs" / "project" / "product" / "idea" / "prd-0002-billing-sync.md"
    initial_content = (
        "---\n"
        "id: PRD-0002\n"
        "title: Billing Sync Engine\n"
        "status: Idea\n"
        "target_persona: Taylor\n"
        "component: billing\n"
        "---\n\n"
        "# PRD-0002: Billing Sync Engine\n\n"
        "## Problem Statement\n"
        "Billing sync needs robust concurrency.\n"
    )
    prd_file.write_text(initial_content, encoding="utf-8")
    bdd_sync_context["prd_path"] = prd_file
    bdd_sync_context["base_hash"] = compute_sha256(initial_content)

    bdd_sync_context["client_draft"] = (
        initial_content + "\n## Checkable Outcomes\n- Client in-flight modification\n"
    )


@when("the corresponding file on disk is modified externally before save")
def file_modified_externally(bdd_sync_context: dict[str, Any]):
    prd_file: Path = bdd_sync_context["prd_path"]
    external_content = (
        "---\n"
        "id: PRD-0002\n"
        "title: Billing Sync Engine\n"
        "status: Idea\n"
        "target_persona: Taylor\n"
        "component: billing\n"
        "---\n\n"
        "# PRD-0002: Billing Sync Engine\n\n"
        "## Problem Statement\n"
        "Billing sync needs robust concurrency.\n\n"
        "## External Notes\n"
        "Edited externally by another teammate.\n"
    )
    prd_file.write_text(external_content, encoding="utf-8")
    bdd_sync_context["external_content"] = external_content


@then("the sync engine detects a hash mismatch conflict")
def sync_engine_detects_conflict(bdd_sync_context: dict[str, Any]):
    prd_file: Path = bdd_sync_context["prd_path"]
    engine: PRDSyncEngine = bdd_sync_context["engine"]
    base_hash: str = bdd_sync_context["base_hash"]
    client_draft: str = bdd_sync_context["client_draft"]

    result = engine.save_draft(prd_file, client_draft, expected_hash=base_hash)
    bdd_sync_context["save_result"] = result

    assert result.status == "conflict"
    assert result.disk_hash != base_hash
    assert result.client_hash == compute_sha256(client_draft)
    assert result.diff_summary != ""


@then("preserves both versions without silent overwrite")
def preserves_both_versions(bdd_sync_context: dict[str, Any]):
    prd_file: Path = bdd_sync_context["prd_path"]
    result = bdd_sync_context["save_result"]
    external_content: str = bdd_sync_context["external_content"]
    client_draft: str = bdd_sync_context["client_draft"]

    # 1. Disk version was NOT overwritten
    disk_content = prd_file.read_text(encoding="utf-8")
    assert disk_content == external_content
    assert "Edited externally by another teammate." in disk_content
    assert "Client in-flight modification" not in disk_content

    # 2. Client version is preserved in conflict file
    assert result.conflict_path is not None
    conflict_file = Path(result.conflict_path)
    assert conflict_file.exists()
    conflict_content = conflict_file.read_text(encoding="utf-8")
    assert conflict_content == client_draft
    assert "Client in-flight modification" in conflict_content
