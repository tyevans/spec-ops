"""Cryptographic Merkle inclusion audit proof generation and offline verification engine (ADR-0016)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from ...config.models import SpecOpsConfig
from .merkle import (
    ComplianceManifest,
    MerkleTree,
    hash_internal_node,
    hash_leaf,
)


def generate_merkle_proof(
    manifest_input: ComplianceManifest | dict[str, Any] | str | Path,
    deliverable_id: str,
) -> dict[str, Any]:
    """Generates a self-contained RFC 6962 / RFC 8785 Merkle inclusion proof for a deliverable."""
    if isinstance(manifest_input, Path):
        manifest_data = json.loads(manifest_input.read_text(encoding="utf-8"))
    elif isinstance(manifest_input, str):
        trimmed = manifest_input.strip()
        if trimmed.startswith("{") and trimmed.endswith("}"):
            manifest_data = json.loads(trimmed)
        else:
            p = Path(manifest_input)
            manifest_data = json.loads(p.read_text(encoding="utf-8"))
    elif isinstance(manifest_input, ComplianceManifest):
        manifest_data = manifest_input.to_dict()
    else:
        manifest_data = dict(manifest_input)

    leaves = manifest_data.get("leaves", [])
    target_leaf: dict[str, Any] | None = None
    target_idx: int | None = None

    clean_target = deliverable_id.upper().replace("TASK-", "").replace("SPIKE-", "").lstrip("0")
    if not clean_target:
        clean_target = deliverable_id.upper()

    for idx, leaf in enumerate(leaves):
        entity_id = str(leaf.get("entity_id", ""))
        task_id = str(leaf.get("data", {}).get("task_id", ""))

        if entity_id == deliverable_id or task_id == deliverable_id:
            target_leaf = leaf
            target_idx = idx
            break

        clean_entity = entity_id.upper().replace("TASK-", "").replace("SPIKE-", "").lstrip("0")
        clean_task = task_id.upper().replace("TASK-", "").replace("SPIKE-", "").lstrip("0")
        if clean_target and (clean_entity == clean_target or clean_task == clean_target):
            target_leaf = leaf
            target_idx = idx
            break

    if target_leaf is None or target_idx is None:
        raise ValueError(f"Deliverable '{deliverable_id}' not found in manifest")

    leaf_hashes = [str(l.get("leaf_hash", "")) for l in leaves]
    tree = MerkleTree(leaf_hashes)
    proof = tree.generate_proof(target_idx)

    return {
        "deliverable_id": target_leaf.get("entity_id", deliverable_id),
        "leaf_index": proof.leaf_index,
        "leaf_hash": proof.leaf_hash,
        "audit_path": [step.to_dict() for step in proof.audit_path],
        "root_hash": proof.root_hash,
        "tree_size": proof.tree_size,
        "standard": manifest_data.get("standard", "soc2"),
        "algorithm": manifest_data.get("algorithm", "sha256"),
        "serialization": manifest_data.get("serialization", "RFC8785"),
        "deliverable_data": target_leaf.get("data", {}),
    }


def verify_merkle_proof(
    proof_input: dict[str, Any] | str | Path,
    trusted_root: str,
) -> tuple[bool, str, dict[str, Any]]:
    """Verifies an inclusion proof against a trusted Merkle root in offline execution."""
    if isinstance(proof_input, Path):
        proof_data = json.loads(proof_input.read_text(encoding="utf-8"))
    elif isinstance(proof_input, str):
        trimmed = proof_input.strip()
        if trimmed.startswith("{") and trimmed.endswith("}"):
            proof_data = json.loads(trimmed)
        else:
            p = Path(proof_input)
            proof_data = json.loads(p.read_text(encoding="utf-8"))
    else:
        proof_data = dict(proof_input)

    deliverable_id = proof_data.get("deliverable_id", "Unknown")
    claimed_leaf_hash = proof_data.get("leaf_hash", "")
    audit_path = proof_data.get("audit_path", [])
    tree_size = proof_data.get("tree_size", 0)

    details: dict[str, Any] = {
        "deliverable_id": deliverable_id,
        "leaf_hash": claimed_leaf_hash,
        "trusted_root": trusted_root,
        "tree_size": tree_size,
        "steps_count": len(audit_path),
    }

    if "deliverable_data" in proof_data:
        computed_leaf = hash_leaf(proof_data["deliverable_data"])
        if computed_leaf != claimed_leaf_hash:
            details["computed_leaf"] = computed_leaf
            return (
                False,
                f"Deliverable payload hash mismatch: recomputed {computed_leaf} != claimed {claimed_leaf_hash}",
                details,
            )

    current = claimed_leaf_hash
    for step in audit_path:
        sibling = step.get("sibling_hash", "")
        is_left = bool(step.get("is_left", False))
        if is_left:
            current = hash_internal_node(sibling, current)
        else:
            current = hash_internal_node(current, sibling)

    details["computed_root"] = current

    if current != trusted_root:
        return (
            False,
            f"Merkle root mismatch: trusted root is {trusted_root}, computed root is {current}",
            details,
        )

    return True, "Proof verified successfully", details


def handle_audit_proof(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Handles 'spec-ops audit proof' CLI command."""
    deliverable_id = getattr(args, "deliverable", None)
    if not deliverable_id:
        print("❌ Error: --deliverable is required", file=sys.stderr)
        return 1

    manifest_arg = getattr(args, "manifest", "dist/compliance/soc2-audit-manifest.json")
    manifest_path = Path(manifest_arg)
    if not manifest_path.is_absolute():
        manifest_path = config.root_dir / manifest_path

    if not manifest_path.is_file():
        err_msg = f"❌ Manifest file not found: {manifest_path}"
        print(err_msg, file=sys.stderr)
        return 1

    try:
        proof_dict = generate_merkle_proof(manifest_path, deliverable_id)
    except Exception as e:
        print(f"❌ Failed to generate Merkle proof: {e}", file=sys.stderr)
        return 1

    out_arg = getattr(args, "out", None)
    if out_arg:
        out_path = Path(out_arg)
        if not out_path.is_absolute():
            out_path = config.root_dir / out_path
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(proof_dict, indent=2, ensure_ascii=False), encoding="utf-8")

    as_json = getattr(args, "json", False)
    if as_json:
        print(json.dumps(proof_dict, indent=2, ensure_ascii=False))
        return 0

    print(f"✨ Merkle Inclusion Proof generated for deliverable '{proof_dict['deliverable_id']}':")
    print(f"   Leaf Index:   {proof_dict['leaf_index']}")
    print(f"   Leaf Hash:    {proof_dict['leaf_hash']}")
    print(f"   Audit Path:   {len(proof_dict['audit_path'])} step(s)")
    print(f"   Merkle Root:  {proof_dict['root_hash']}")
    print(f"   Tree Size:    {proof_dict['tree_size']}")
    if out_arg:
        print(f"   Saved to:     {out_path}")
    return 0


def handle_audit_verify_proof(args: argparse.Namespace, config: SpecOpsConfig) -> int:
    """Handles 'spec-ops audit verify-proof' CLI command."""
    proof_arg = getattr(args, "proof_file", None)
    if not proof_arg:
        print("❌ Error: proof_file positional argument is required", file=sys.stderr)
        return 1

    proof_path = Path(proof_arg)
    if not proof_path.is_absolute():
        proof_path = config.root_dir / proof_path

    if not proof_path.is_file():
        err_msg = f"❌ Proof file not found: {proof_path}"
        print(err_msg, file=sys.stderr)
        return 1

    trusted_root = getattr(args, "root", "")
    if not trusted_root:
        print("❌ Error: --root is required", file=sys.stderr)
        return 1

    ok, msg, details = verify_merkle_proof(proof_path, trusted_root)
    as_json = getattr(args, "json", False)

    if as_json:
        result_payload = {
            "ok": ok,
            "deliverable_id": details.get("deliverable_id"),
            "leaf_hash": details.get("leaf_hash"),
            "root_hash": trusted_root,
            "computed_root": details.get("computed_root"),
            "tree_size": details.get("tree_size"),
            "steps_count": details.get("steps_count"),
        }
        if not ok:
            result_payload["error"] = msg
        print(json.dumps(result_payload, indent=2, ensure_ascii=False))
        return 0 if ok else 1

    if ok:
        print("✅ Merkle Inclusion Proof verified successfully:")
        print(f"   Deliverable:  {details.get('deliverable_id', 'Unknown')}")
        print(f"   Leaf Hash:    {details.get('leaf_hash')}")
        print(f"   Trusted Root: {trusted_root}")
        print(f"   Audit Path:   {details.get('steps_count', 0)} step(s)")
        print(f"   Tree Size:    {details.get('tree_size', 0)}")
        return 0

    print("❌ Merkle Inclusion Proof verification failed:", file=sys.stderr)
    print(f"   Deliverable:   {details.get('deliverable_id', 'Unknown')}", file=sys.stderr)
    print(f"   Error:         {msg}", file=sys.stderr)
    print(f"   Trusted Root:  {trusted_root}", file=sys.stderr)
    if "computed_root" in details:
        print(f"   Computed Root: {details['computed_root']}", file=sys.stderr)
    return 1
