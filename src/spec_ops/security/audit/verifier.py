"""Cryptographic compliance audit verifier and tamper detection engine (ADR-0016)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ...core.parser import extract_frontmatter, parse_task
from .exporter import (
    _extract_story_scenarios,
    _resolve_task_commit_sha,
    _resolve_task_signoff,
)
from .merkle import (
    ComplianceDeliverable,
    ComplianceManifest,
    MerkleTree,
    hash_leaf,
    verify_inclusion_proof,
)


@dataclass
class VerificationResult:
    """Outcome of compliance audit trail verification across manifest and disk state."""

    ok: bool
    root_hash: str
    deliverables_checked: int = 0
    errors: list[str] = field(default_factory=list)
    corrupted_entity_id: str | None = None
    expected_hash: str | None = None
    computed_hash: str | None = None


def verify_compliance_manifest(
    manifest_input: ComplianceManifest | dict[str, Any] | str | Path,
) -> tuple[bool, list[str]]:
    """Verifies compliance manifest internal integrity and recomputes the Merkle root hash."""
    if isinstance(manifest_input, Path):
        data = json.loads(manifest_input.read_text(encoding="utf-8"))
    elif isinstance(manifest_input, str):
        trimmed = manifest_input.strip()
        if trimmed.startswith("{") and trimmed.endswith("}"):
            data = json.loads(trimmed)
        else:
            p = Path(manifest_input)
            data = json.loads(p.read_text(encoding="utf-8") if p.is_file() else manifest_input)
    elif isinstance(manifest_input, ComplianceManifest):
        data = manifest_input.to_dict()
    else:
        data = dict(manifest_input)

    errors: list[str] = []
    expected_root = data.get("root_hash", "")
    recomputed_hashes: list[str] = []

    for leaf in data.get("leaves", []):
        idx = leaf.get("index")
        entity_id = leaf.get("entity_id", f"leaf-{idx}")
        claimed_hash = leaf.get("leaf_hash", "")
        actual_hash = hash_leaf(leaf.get("data", {}))

        if actual_hash != claimed_hash:
            errors.append(
                f"Tampered deliverable '{entity_id}' at index {idx}: expected {claimed_hash}, recomputed {actual_hash}"
            )
        recomputed_hashes.append(actual_hash)

    tree = MerkleTree(recomputed_hashes)
    if tree.root_hash != expected_root:
        errors.append(
            f"Merkle root mismatch: manifest claims {expected_root}, recomputed tree root is {tree.root_hash}"
        )

    return len(errors) == 0, errors


def verify_audit_trail(
    manifest_path: Path | str,
    repo_dir: Path | str = ".",
) -> VerificationResult:
    """Verifies compliance manifest against repository disk state and git history."""
    p = Path(manifest_path)
    if not p.is_file():
        return VerificationResult(
            ok=False,
            root_hash="",
            errors=[f"Manifest file not found: {manifest_path}"],
            corrupted_entity_id="MANIFEST_FILE",
            expected_hash=None,
            computed_hash=None,
        )

    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception as e:
        return VerificationResult(
            ok=False,
            root_hash="",
            errors=[f"Failed to parse manifest JSON: {e}"],
            corrupted_entity_id="MANIFEST_JSON",
            expected_hash=None,
            computed_hash=None,
        )

    expected_root = data.get("root_hash", "")
    leaves = data.get("leaves", [])

    # Phase 1: Internal Merkle leaf and root verification
    recomputed_hashes: list[str] = []
    for leaf in leaves:
        idx = leaf.get("index")
        entity_id = leaf.get("entity_id", f"leaf-{idx}")
        claimed_hash = leaf.get("leaf_hash", "")
        actual_hash = hash_leaf(leaf.get("data", {}))

        if actual_hash != claimed_hash:
            return VerificationResult(
                ok=False,
                root_hash=expected_root,
                deliverables_checked=len(recomputed_hashes),
                errors=[
                    f"Tampered deliverable '{entity_id}' at index {idx}: expected {claimed_hash}, recomputed {actual_hash}"
                ],
                corrupted_entity_id=entity_id,
                expected_hash=claimed_hash,
                computed_hash=actual_hash,
            )
        recomputed_hashes.append(actual_hash)

    tree = MerkleTree(recomputed_hashes)
    if tree.root_hash != expected_root:
        return VerificationResult(
            ok=False,
            root_hash=expected_root,
            deliverables_checked=len(recomputed_hashes),
            errors=[
                f"Merkle root mismatch: manifest claims {expected_root}, recomputed tree root is {tree.root_hash}"
            ],
            corrupted_entity_id="MERKLE_ROOT",
            expected_hash=expected_root,
            computed_hash=tree.root_hash,
        )

    # Phase 2: Companion MERKLE_ROOT verification
    root_companion = p.parent / "MERKLE_ROOT"
    if root_companion.is_file():
        companion_hash = root_companion.read_text(encoding="utf-8").strip()
        if companion_hash != expected_root:
            return VerificationResult(
                ok=False,
                root_hash=expected_root,
                deliverables_checked=len(leaves),
                errors=[
                    f"Companion MERKLE_ROOT mismatch: expected {expected_root}, found {companion_hash}"
                ],
                corrupted_entity_id="MERKLE_ROOT",
                expected_hash=expected_root,
                computed_hash=companion_hash,
            )

    # Phase 3: External repository disk state & git traceability verification
    repo_path = Path(repo_dir).resolve()
    complete_dir = repo_path / "docs" / "project" / "backlog" / "complete"

    for leaf in leaves:
        leaf_data = leaf.get("data", {})
        task_id = leaf_data.get("task_id", "")
        clean_id = task_id.upper().replace("TASK-", "").replace("SPIKE-", "").lstrip("0")
        if not clean_id:
            clean_id = task_id

        matched_files = [
            f for f in sorted(complete_dir.glob("*.md"))
            if not f.name.startswith(".") and (f"-{clean_id}-" in f.name or f.name.startswith(f"0{clean_id}-") or f.name.startswith(f"{clean_id.zfill(4)}-") or f.name.startswith(f"{clean_id}-"))
        ]

        if not matched_files:
            return VerificationResult(
                ok=False,
                root_hash=expected_root,
                deliverables_checked=len(leaves),
                errors=[f"Broken traceability: task file for '{task_id}' not found in {complete_dir}"],
                corrupted_entity_id=task_id,
                expected_hash=leaf.get("leaf_hash"),
                computed_hash="FILE_NOT_FOUND",
            )

        task_file = matched_files[0]
        content_bytes = task_file.read_bytes()
        actual_prompt_sha = hashlib.sha256(content_bytes).hexdigest()
        claimed_prompt_sha = leaf_data.get("prompt_sha256", "")

        meta, _ = extract_frontmatter(task_file.read_text(encoding="utf-8"))
        task = parse_task(task_file)

        # Detect out-of-band tampering in task file, commit SHA, or sign-off signature
        disk_commit_sha = _resolve_task_commit_sha(repo_path, task_id, meta)
        disk_signoff = _resolve_task_signoff(task_id, meta, task.signed_off_by, task.signed_off_at)
        disk_test_digest = str(
            meta.get("test_results_digest")
            or hashlib.sha256(f"passed:{task_id}".encode("utf-8")).hexdigest()
        )
        disk_scenarios = _extract_story_scenarios(repo_path, sorted(task.governing_stories))

        disk_deliverable = ComplianceDeliverable(
            task_id=task_id,
            prd_id=task.governing_prds[0] if task.governing_prds else "PRD-0000",
            story_ids=sorted(task.governing_stories),
            commit_sha=disk_commit_sha,
            prompt_sha256=actual_prompt_sha,
            test_results_digest=disk_test_digest,
            human_signoff=disk_signoff,
            gherkin_scenarios=disk_scenarios,
            metadata={"target_bc": task.target_bc, "title": task.title},
        )
        disk_leaf_hash = disk_deliverable.compute_leaf_hash()
        claimed_leaf_hash = leaf.get("leaf_hash", "")

        if actual_prompt_sha != claimed_prompt_sha or disk_leaf_hash != claimed_leaf_hash:
            return VerificationResult(
                ok=False,
                root_hash=expected_root,
                deliverables_checked=len(leaves),
                errors=[
                    f"Out-of-band audit trail tampering detected in task '{task_id}': disk state diverged from manifest."
                ],
                corrupted_entity_id=task_id,
                expected_hash=claimed_leaf_hash,
                computed_hash=disk_leaf_hash,
            )

    return VerificationResult(
        ok=True,
        root_hash=expected_root,
        deliverables_checked=len(leaves),
        errors=[],
        corrupted_entity_id=None,
        expected_hash=None,
        computed_hash=None,
    )
