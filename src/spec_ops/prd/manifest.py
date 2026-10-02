"""Cryptographic release reconciliation manifests and headless SHA-256 verification."""

from __future__ import annotations

import datetime
import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..security.digest import compute_git_tree_digest
from .uat_receipt import serialize_canonical_json


def compute_manifest_signature(
    prd_id: str,
    tree_digest: str,
    completed_tasks: list[dict[str, str]],
    test_summary: dict[str, Any],
    uat_summary: dict[str, Any],
) -> str:
    """Computes cryptographic SHA-256 signature sealing manifest fields together."""
    payload = (
        f"PRD:{prd_id}\n"
        f"TREE:{tree_digest}\n"
        f"TASKS:{serialize_canonical_json(completed_tasks)}"
        f"TESTS:{serialize_canonical_json(test_summary)}"
        f"UAT:{serialize_canonical_json(uat_summary)}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_release_manifest(
    repo_root: Path | str,
    prd_id: str,
    prd_title: str,
    target_persona: str,
    completed_tasks: list[dict[str, str]],
    test_summary: dict[str, Any],
    uat_summary: dict[str, Any],
    output_path: Path | str | None = None,
    allow_uncommitted: bool = False,
) -> dict[str, Any]:
    """Generates a cryptographic release reconciliation manifest."""
    root = Path(repo_root).resolve()
    tree_digest, clean, errs = compute_git_tree_digest(root, allow_uncommitted=allow_uncommitted)
    if errs:
        raise ValueError(f"Cannot generate release manifest: {'; '.join(errs)}")

    signature = compute_manifest_signature(
        prd_id=prd_id,
        tree_digest=tree_digest,
        completed_tasks=completed_tasks,
        test_summary=test_summary,
        uat_summary=uat_summary,
    )

    manifest_data: dict[str, Any] = {
        "$schema": "spec-ops/release-manifest-v1",
        "version": "1.0",
        "prd": {
            "id": prd_id,
            "title": prd_title,
            "persona": target_persona,
        },
        "verified_tree_digest": tree_digest,
        "completed_tasks": completed_tasks,
        "test_verification": test_summary,
        "uat_verification": uat_summary,
        "manifest_signature": signature,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    if output_path:
        out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(serialize_canonical_json(manifest_data), encoding="utf-8")

    return manifest_data


def verify_release_manifest(
    manifest: dict[str, Any] | Path | str,
    repo_root: Path | str,
) -> tuple[bool, list[str]]:
    """Verifies that repository state, signatures, and UAT sign-offs match manifest in <50ms."""
    violations: list[str] = []
    root = Path(repo_root).resolve()

    if isinstance(manifest, (str, Path)):
        p = Path(manifest).resolve()
        if not p.is_file():
            return False, [f"Manifest file does not exist: {p}"]
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            return False, [f"Malformed manifest JSON: {e}"]
    elif isinstance(manifest, dict):
        data = manifest
    else:
        return False, ["Manifest must be a dict or file path."]

    # 1. Structural checks
    required_keys = [
        "prd",
        "verified_tree_digest",
        "completed_tasks",
        "test_verification",
        "uat_verification",
        "manifest_signature",
    ]
    for rk in required_keys:
        if rk not in data:
            violations.append(f"Missing required manifest field: '{rk}'.")

    if violations:
        return False, violations

    prd = data["prd"]
    tree_digest = data["verified_tree_digest"]
    completed_tasks = data["completed_tasks"]
    test_summary = data["test_verification"]
    uat_summary = data["uat_verification"]
    manifest_signature = data["manifest_signature"]

    # 2. Verify cryptographic signature
    expected_sig = compute_manifest_signature(
        prd_id=prd.get("id", ""),
        tree_digest=tree_digest,
        completed_tasks=completed_tasks,
        test_summary=test_summary,
        uat_summary=uat_summary,
    )
    if expected_sig != manifest_signature:
        violations.append(
            f"Cryptographic signature invalid: expected {expected_sig[:12]}..., got {manifest_signature[:12]}..."
        )

    # 3. Verify repository cleanliness and tree digest
    curr_tree, clean, errs = compute_git_tree_digest(root, allow_uncommitted=False)
    if errs:
        violations.extend(errs)
    elif curr_tree != tree_digest:
        violations.append(
            f"Tampering detected: repository tree SHA-256 ({curr_tree[:12]}...) does not match manifest ({tree_digest[:12]}...)."
        )

    # 4. Verify test outcomes (100% pass rate requirement)
    if test_summary.get("status") != "Passed (CI)" or test_summary.get("failed_scenarios", 0) > 0:
        violations.append(
            f"Test verification failure: status is '{test_summary.get('status')}', failed={test_summary.get('failed_scenarios', 0)}."
        )

    # 5. Verify UAT sign-off approval
    if uat_summary.get("status") != "Approved":
        violations.append(
            f"UAT sign-off failure: status is '{uat_summary.get('status')}'; mandatory PM UAT approval required."
        )

    return len(violations) == 0, violations
