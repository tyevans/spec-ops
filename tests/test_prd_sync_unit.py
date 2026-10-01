"""Comprehensive unit and blackbox frontdoor tests for PRD sync and auto-save engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0009, ADR-0013; PRD-0003; US-0044, US-0045.
"""

from __future__ import annotations

import json
from http.client import HTTPConnection
from http.server import HTTPServer
from pathlib import Path
import threading
import time

import pytest

from spec_ops.config.models import SpecOpsConfig
from spec_ops.visualizer.prd_sync import (
    PRDSyncEngine,
    SyncResult,
    compute_sha256,
    find_prd_file,
    get_draft_status,
    handle_prd_draft_get,
    handle_prd_save_post,
    save_draft,
)
from spec_ops.visualizer.server import VisualizerHandler


def test_compute_sha256():
    """Asserts SHA-256 computation matches standard hexadecimal digest."""
    empty_digest = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert compute_sha256("") == empty_digest
    assert compute_sha256(b"") == empty_digest

    text = "SpecOps PRD Studio Auto-Save"
    digest = compute_sha256(text)
    assert len(digest) == 64
    assert digest == compute_sha256(text.encode("utf-8"))


def test_save_draft_new_file(tmp_path: Path):
    """Asserts saving to a new file path creates parent dirs and saves cleanly."""
    target = tmp_path / "docs" / "project" / "product" / "idea" / "prd-0010-new.md"
    content = "# PRD-0010: New Idea\n\n## Problem Statement\nTesting save.\n"

    result = save_draft(target, content)
    assert result.status == "saved"
    assert result.revision_digest == compute_sha256(content)
    assert result.disk_hash == result.revision_digest
    assert result.client_hash == result.revision_digest
    assert result.diff_summary == ""
    assert result.conflict_path is None
    assert target.exists()
    assert target.read_text(encoding="utf-8") == content


def test_save_draft_existing_matching_hash(tmp_path: Path):
    """Asserts saving with matching expected_hash updates file and returns new hash."""
    target = tmp_path / "prd.md"
    initial_content = "# Version 1\n"
    target.write_text(initial_content, encoding="utf-8")
    initial_hash = compute_sha256(initial_content)

    updated_content = "# Version 2\n"
    result = save_draft(target, updated_content, expected_hash=initial_hash)

    assert result.status == "saved"
    assert result.revision_digest == compute_sha256(updated_content)
    assert target.read_text(encoding="utf-8") == updated_content


def test_save_draft_conflict_preserves_both(tmp_path: Path):
    """Asserts external modifications cause conflict, preserving disk state and saving client draft."""
    target = tmp_path / "prd-conflict.md"
    initial_content = "# Version 1\n"
    target.write_text(initial_content, encoding="utf-8")
    base_hash = compute_sha256(initial_content)

    # External edit writes Version 2
    external_content = "# Version 2 - External\n"
    target.write_text(external_content, encoding="utf-8")
    external_hash = compute_sha256(external_content)

    # Client tries to save Version 3 expecting base_hash
    client_content = "# Version 3 - Client Draft\n"
    result = save_draft(target, client_content, expected_hash=base_hash)

    assert result.status == "conflict"
    assert result.disk_hash == external_hash
    assert result.client_hash == compute_sha256(client_content)
    assert "Conflict detected" in result.message
    assert result.diff_summary != ""
    assert result.conflict_path is not None

    # Verify disk content was not overwritten
    assert target.read_text(encoding="utf-8") == external_content

    # Verify client draft was saved to conflict file
    conflict_file = Path(result.conflict_path)
    assert conflict_file.exists()
    assert conflict_file.read_text(encoding="utf-8") == client_content


def test_save_draft_error_handling(tmp_path: Path):
    """Asserts save_draft catches IO exceptions and returns error status."""
    target_dir = tmp_path / "a_directory"
    target_dir.mkdir()

    # Attempting to write text to an existing directory path fails cleanly
    result = save_draft(target_dir, "content")
    assert result.status == "error"
    assert result.revision_digest == ""
    assert len(result.message) > 0


def test_get_draft_status(tmp_path: Path):
    """Asserts get_draft_status correctly reflects on-disk state."""
    target = tmp_path / "draft.md"

    # Non-existing file
    status = get_draft_status(target)
    assert status["exists"] is False
    assert status["content"] == ""
    assert status["size"] == 0

    # Existing file
    content = "# PRD Draft\n"
    target.write_text(content, encoding="utf-8")
    status = get_draft_status(target)
    assert status["exists"] is True
    assert status["content"] == content
    assert status["digest"] == compute_sha256(content)
    assert status["last_modified"] > 0
    assert status["size"] == len(content.encode("utf-8"))


def test_prd_sync_engine_debouncing(tmp_path: Path):
    """Asserts PRDSyncEngine properly debounces rapid draft edits."""
    engine = PRDSyncEngine(repo_root=tmp_path, debounce_interval=0.05)
    prd_path = tmp_path / "debounced.md"

    callback_results: list[SyncResult] = []

    def on_saved(res: SyncResult):
        callback_results.append(res)

    # Trigger multiple rapid edits
    for i in range(5):
        engine.debounce_save(prd_path, f"# Edit {i}\n", callback=on_saved)

    # Wait for debounce timer to fire
    time.sleep(0.1)

    assert prd_path.exists()
    assert prd_path.read_text(encoding="utf-8") == "# Edit 4\n"
    assert len(callback_results) == 1
    assert callback_results[0].status == "saved"
    assert callback_results[0].revision_digest == compute_sha256("# Edit 4\n")


def test_prd_sync_engine_cancel_and_flush(tmp_path: Path):
    """Asserts cancelling and manual flushing of pending debounced writes."""
    engine = PRDSyncEngine(repo_root=tmp_path, debounce_interval=10.0)
    prd_path = tmp_path / "flush_test.md"

    # Queue debounced write
    engine.debounce_save(prd_path, "# Queued Content\n")

    # Cancel
    engine.cancel_pending(prd_path)
    assert not prd_path.exists()

    # Queue again and manually flush
    engine.debounce_save(prd_path, "# Flushed Content\n")
    results = engine.flush_pending(prd_path)
    assert len(results) == 1
    assert results[0].status == "saved"
    assert prd_path.read_text(encoding="utf-8") == "# Flushed Content\n"

    # Check revision history
    history = engine.get_revision_history(prd_path)
    assert len(history) == 1
    assert history[0] == compute_sha256("# Flushed Content\n")


def test_find_prd_file(tmp_path: Path):
    """Asserts locating PRD files across docs/project/product/ subfolders."""
    idea_dir = tmp_path / "docs" / "project" / "product" / "idea"
    idea_dir.mkdir(parents=True, exist_ok=True)
    target = idea_dir / "prd-0042-machine-learning.md"
    target.write_text("# PRD-0042\n", encoding="utf-8")

    assert find_prd_file(tmp_path, "PRD-0042") == target
    assert find_prd_file(tmp_path, "0042") == target
    assert find_prd_file(tmp_path, "prd-0042") == target
    assert find_prd_file(tmp_path, "PRD-9999") is None


def test_handle_prd_draft_get_and_save_post(tmp_path: Path):
    """Asserts handler functions for GET /api/prd/draft and POST /api/prd/save."""
    prd_dir = tmp_path / "docs" / "project" / "product" / "idea"
    prd_dir.mkdir(parents=True, exist_ok=True)
    prd_file = prd_dir / "prd-0001-test.md"
    content = "# Test PRD\n"
    prd_file.write_text(content, encoding="utf-8")

    # 1. GET with path
    code, res = handle_prd_draft_get(tmp_path, {"path": ["docs/project/product/idea/prd-0001-test.md"]})
    assert code == 200
    assert res["content"] == content
    assert res["digest"] == compute_sha256(content)

    # 2. GET with prd_id
    code, res = handle_prd_draft_get(tmp_path, {"prd": ["PRD-0001"]})
    assert code == 200
    assert res["content"] == content

    # 3. GET missing params
    code, res = handle_prd_draft_get(tmp_path, {})
    assert code == 400

    # 4. GET non-existent
    code, res = handle_prd_draft_get(tmp_path, {"prd": ["PRD-9999"]})
    assert code == 404

    # 5. POST save successfully
    new_content = "# Updated PRD\n"
    code, res = handle_prd_save_post(
        tmp_path,
        {"file_path": "docs/project/product/idea/prd-0001-test.md", "content": new_content},
    )
    assert code == 200
    assert res["status"] == "saved"
    assert res["revision_digest"] == compute_sha256(new_content)

    # 6. POST save conflict
    conflict_content = "# Conflict PRD\n"
    code, res = handle_prd_save_post(
        tmp_path,
        {
            "file_path": "docs/project/product/idea/prd-0001-test.md",
            "content": conflict_content,
            "expected_hash": "stale_hash",
        },
    )
    assert code == 409
    assert res["status"] == "conflict"

    # 7. POST save debounce queue
    code, res = handle_prd_save_post(
        tmp_path,
        {
            "file_path": "docs/project/product/idea/prd-0001-test.md",
            "content": "# Queued\n",
            "debounce": True,
        },
    )
    assert code == 202
    assert res["status"] == "pending"


@pytest.fixture
def running_studio_server(tmp_path: Path):
    """Spins up VisualizerHandler HTTP server for blackbox HTTP verification."""
    config = SpecOpsConfig(root_dir=tmp_path)

    class CustomHandler(VisualizerHandler):
        pass

    CustomHandler.config = config
    server = HTTPServer(("127.0.0.1", 0), CustomHandler)
    port = server.server_port
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()

    yield f"127.0.0.1:{port}", tmp_path

    server.shutdown()
    server.server_close()


def test_server_api_prd_draft_and_save_http(running_studio_server):
    """Blackbox HTTP verification of /api/prd/draft (GET) and /api/prd/save (POST)."""
    addr, root = running_studio_server
    host, port = addr.split(":")

    idea_dir = root / "docs" / "project" / "product" / "idea"
    idea_dir.mkdir(parents=True, exist_ok=True)
    prd_file = idea_dir / "prd-0005-sync.md"
    initial_content = "# PRD-0005: Studio Sync\n\n## Checkable Outcomes\n- Zero daemon architecture\n"
    prd_file.write_text(initial_content, encoding="utf-8")

    # 1. GET /api/prd/draft
    conn = HTTPConnection(host, int(port))
    conn.request("GET", "/api/prd/draft?prd=PRD-0005")
    res = conn.getresponse()
    assert res.status == 200
    data = json.loads(res.read().decode("utf-8"))
    assert data["exists"] is True
    assert data["content"] == initial_content
    base_digest = data["revision_digest"]
    assert base_digest == compute_sha256(initial_content)

    # 2. POST /api/prd/save (Success)
    conn = HTTPConnection(host, int(port))
    save_payload = json.dumps(
        {
            "file_path": "docs/project/product/idea/prd-0005-sync.md",
            "content": initial_content + "- Debounced auto-save\n",
            "expected_hash": base_digest,
        }
    )
    conn.request("POST", "/api/prd/save", body=save_payload, headers={"Content-Type": "application/json"})
    res = conn.getresponse()
    assert res.status == 200
    save_data = json.loads(res.read().decode("utf-8"))
    assert save_data["status"] == "saved"
    new_digest = save_data["revision_digest"]

    # 3. POST /api/prd/save (Conflict)
    conn = HTTPConnection(host, int(port))
    conflict_payload = json.dumps(
        {
            "file_path": "docs/project/product/idea/prd-0005-sync.md",
            "content": initial_content + "- Conflicting client edit\n",
            "expected_hash": base_digest,  # Obsolete digest!
        }
    )
    conn.request("POST", "/api/prd/save", body=conflict_payload, headers={"Content-Type": "application/json"})
    res = conn.getresponse()
    assert res.status == 409
    conflict_data = json.loads(res.read().decode("utf-8"))
    assert conflict_data["status"] == "conflict"
    assert conflict_data["disk_hash"] == new_digest
    assert conflict_data["diff_summary"] != ""
    assert conflict_data["conflict_path"] is not None
