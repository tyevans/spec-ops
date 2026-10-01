"""BDD step implementations for US-0056 Merkle compliance manifest (ADR-0003, ADR-0006)."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, scenarios, then, when

SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
CLI_ENV = {**os.environ, "PYTHONPATH": f"{SRC_DIR}:{os.environ.get('PYTHONPATH', '')}".rstrip(":")}

scenarios("features/us_0056_merkle_manifest.feature")


@pytest.fixture
def bdd_merkle_context(tmp_path: Path) -> dict[str, Any]:
    """Scaffolds a clean git repository containing specifications and source code."""
    repo = tmp_path / "repo"
    repo.mkdir()

    subprocess.run(["git", "init", "-b", "main"], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Auditor"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "auditor@specops.dev"], cwd=repo, check=True)

    prd_dir = repo / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True)
    (prd_dir / "prd-0002.md").write_text("# PRD-0002: Security & Compliance\nScope and details.", encoding="utf-8")

    adr_dir = repo / "docs" / "project" / "adrs" / "accepted"
    adr_dir.mkdir(parents=True)
    (adr_dir / "adr-0016.md").write_text("# ADR-0016: Merkle Manifest\nArchitecture decision.", encoding="utf-8")

    backlog_dir = repo / "docs" / "project" / "backlog" / "complete"
    backlog_dir.mkdir(parents=True)
    (backlog_dir / "0141.md").write_text("# TASK-0141\nCompleted task contract.", encoding="utf-8")

    src_dir = repo / "src" / "spec_ops"
    src_dir.mkdir(parents=True)
    (src_dir / "core.py").write_text('"""Core module."""\nVERSION = "1.0.0"\n', encoding="utf-8")

    (repo / "specops.toml").write_text('[project]\nname = "MerkleProject"\n', encoding="utf-8")

    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-m", "chore: initial commit"], cwd=repo, check=True)

    return {
        "repo": repo,
        "tampered_file": None,
        "cli_result": None,
        "root_hash": None,
    }


@given("a project repository with accepted PRDs, ADRs, and tasks")
def project_repository_with_artifacts(bdd_merkle_context: dict[str, Any]):
    repo: Path = bdd_merkle_context["repo"]
    assert (repo / "docs" / "project" / "product" / "accepted" / "prd-0002.md").exists()
    assert (repo / "docs" / "project" / "adrs" / "accepted" / "adr-0016.md").exists()
    assert (repo / "docs" / "project" / "backlog" / "complete" / "0141.md").exists()
    assert (repo / "src" / "spec_ops" / "core.py").exists()


@when('the auditor runs "spec-ops audit merkle"')
def auditor_runs_audit_merkle(bdd_merkle_context: dict[str, Any]):
    repo: Path = bdd_merkle_context["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "audit", "merkle"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_merkle_context["cli_result"] = res


@then("a deterministic Merkle root hash is generated")
def deterministic_merkle_root_hash_generated(bdd_merkle_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_merkle_context["cli_result"]
    assert res.returncode == 0
    match = re.search(r"Merkle Root:\s+([a-f0-9]{64})", res.stdout)
    assert match is not None, f"Expected 64-hex Merkle root hash in stdout, got:\n{res.stdout}"
    bdd_merkle_context["root_hash"] = match.group(1)


@then("each leaf node corresponds to a version-controlled specification or source artifact")
def leaves_correspond_to_artifacts(bdd_merkle_context: dict[str, Any]):
    repo: Path = bdd_merkle_context["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "audit", "merkle", "--json"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res.returncode == 0
    data = json.loads(res.stdout)
    leaves = data.get("leaves", [])
    assert len(leaves) >= 4

    for leaf in leaves:
        rel_path = leaf.get("entity_id")
        assert rel_path.startswith("docs/project/") or rel_path.startswith("src/"), f"Unexpected artifact path: {rel_path}"
        assert (repo / rel_path).is_file(), f"Artifact referenced in leaf missing on disk: {rel_path}"


@given("a verified Merkle compliance manifest")
def verified_merkle_compliance_manifest(bdd_merkle_context: dict[str, Any]):
    repo: Path = bdd_merkle_context["repo"]
    res_gen = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "audit", "merkle", "--output", "manifest.json"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res_gen.returncode == 0
    assert (repo / "manifest.json").exists()

    res_verify = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "audit", "merkle", "--verify", "manifest.json"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    assert res_verify.returncode == 0


@when('a file in "docs/project/" is modified without updating the manifest')
def file_in_docs_project_modified(bdd_merkle_context: dict[str, Any]):
    repo: Path = bdd_merkle_context["repo"]
    target_rel = "docs/project/product/accepted/prd-0002.md"
    target_abs = repo / target_rel
    original_text = target_abs.read_text(encoding="utf-8")
    target_abs.write_text(original_text + "\n# UNAUTHORIZED TAMPERING\n", encoding="utf-8")
    bdd_merkle_context["tampered_file"] = target_rel


@then('running "spec-ops audit merkle --verify manifest.json" detects a digest mismatch')
def run_verify_detects_digest_mismatch(bdd_merkle_context: dict[str, Any]):
    repo: Path = bdd_merkle_context["repo"]
    res = subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", "audit", "merkle", "--verify", "manifest.json"],
        cwd=str(repo),
        capture_output=True,
        text=True,
        env=CLI_ENV,
    )
    bdd_merkle_context["cli_result"] = res
    assert res.returncode == 1
    combined_output = (res.stdout + res.stderr).lower()
    assert "digest mismatch" in combined_output


@then("identifies the exact tampered file path")
def identifies_exact_tampered_file_path(bdd_merkle_context: dict[str, Any]):
    res: subprocess.CompletedProcess = bdd_merkle_context["cli_result"]
    tampered_file = bdd_merkle_context["tampered_file"]
    combined_output = res.stdout + res.stderr
    assert tampered_file in combined_output
