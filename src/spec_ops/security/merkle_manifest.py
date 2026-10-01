"""Tamper-evident Merkle compliance manifest generator and verifier (ADR-0016).

Computes deterministic SHA-256 leaf digests across version-locked artifacts in
docs/project/ and src/, constructing a balanced binary Merkle tree conforming to
RFC 6962 and RFC 8785.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .audit.merkle import (
    EMPTY_ROOT_HASH,
    LEAF_PREFIX,
    NODE_PREFIX,
    MerkleInclusionProof,
    MerkleTree,
    hash_leaf,
    verify_inclusion_proof,
)


@dataclass
class MerkleVerificationResult:
    """Outcome of Merkle compliance manifest integrity verification against repository state."""

    ok: bool
    root_hash: str
    expected_root: str
    artifacts_checked: int = 0
    tampered_files: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    corrupted_entity_id: str | None = None
    expected_hash: str | None = None
    computed_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "root_hash": self.root_hash,
            "expected_root": self.expected_root,
            "artifacts_checked": self.artifacts_checked,
            "tampered_files": list(self.tampered_files),
            "errors": list(self.errors),
            "corrupted_entity_id": self.corrupted_entity_id,
            "expected_hash": self.expected_hash,
            "computed_hash": self.computed_hash,
        }


@dataclass
class MerkleManifest:
    """Cryptographic Merkle tree compliance manifest binding version-locked artifacts."""

    version: str = "1.0.0"
    standard: str = "soc2"
    generated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    root_hash: str = ""
    algorithm: str = "sha256"
    serialization: str = "RFC8785"
    leaf_prefix: str = "00"
    node_prefix: str = "01"
    tree_size: int = 0
    leaves: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "standard": self.standard,
            "generated_at": self.generated_at,
            "root_hash": self.root_hash,
            "algorithm": self.algorithm,
            "serialization": self.serialization,
            "leaf_prefix": self.leaf_prefix,
            "node_prefix": self.node_prefix,
            "tree_size": self.tree_size,
            "leaves": self.leaves,
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def generate_proof(self, file_path: str) -> dict[str, Any]:
        """Generates an RFC 6962 Merkle inclusion proof for a single specification or source file."""
        return generate_file_proof(self, file_path)


def collect_project_artifacts(repo_root: Path | str) -> dict[str, bytes]:
    """Scans docs/project/ and src/ for version-locked files, ignoring non-deterministic caches."""
    repo = Path(repo_root).resolve()
    artifacts: dict[str, bytes] = {}

    target_dirs = ["docs/project", "src"]
    for rel_dir in target_dirs:
        dir_path = repo / rel_dir
        if not dir_path.is_dir():
            continue
        for root, dirs, files in os.walk(dir_path):
            dirs[:] = [d for d in dirs if d != "__pycache__" and not d.startswith(".")]
            for f in sorted(files):
                if f.startswith(".") or f.endswith((".pyc", ".pyo", ".swp", ".tmp")) or f.endswith("~"):
                    continue
                file_p = Path(root) / f
                if not file_p.is_file():
                    continue
                rel_p = file_p.relative_to(repo).as_posix()
                artifacts[rel_p] = file_p.read_bytes()

    return artifacts


def build_merkle_manifest(
    artifacts: dict[str, bytes | str],
    standard: str = "soc2",
    generated_at: str | None = None,
) -> MerkleManifest:
    """Constructs a deterministic Merkle compliance manifest from a dictionary of file paths and contents."""
    sorted_items = sorted(artifacts.items(), key=lambda kv: kv[0])
    leaves: list[dict[str, Any]] = []
    leaf_hashes: list[str] = []

    for idx, (path, content) in enumerate(sorted_items):
        raw_bytes = content.encode("utf-8") if isinstance(content, str) else content
        file_sha256 = hashlib.sha256(raw_bytes).hexdigest()
        leaf_data = {"path": path, "sha256": file_sha256, "size": len(raw_bytes)}
        l_hash = hash_leaf(leaf_data)
        leaf_hashes.append(l_hash)
        leaves.append({
            "index": idx,
            "leaf_hash": l_hash,
            "entity_id": path,
            "data": leaf_data,
        })

    tree = MerkleTree(leaf_hashes)
    timestamp = generated_at or datetime.now(timezone.utc).isoformat()
    return MerkleManifest(
        version="1.0.0",
        standard=standard,
        generated_at=timestamp,
        root_hash=tree.root_hash,
        algorithm="sha256",
        serialization="RFC8785",
        leaf_prefix=LEAF_PREFIX.hex(),
        node_prefix=NODE_PREFIX.hex(),
        tree_size=len(leaves),
        leaves=leaves,
    )


def generate_merkle_manifest(
    repo_root: Path | str = ".",
    standard: str = "soc2",
    output_path: Path | str | None = None,
) -> MerkleManifest:
    """Scans repository artifacts and generates a Merkle compliance manifest, optionally writing to disk."""
    artifacts = collect_project_artifacts(repo_root)
    manifest = build_merkle_manifest(artifacts, standard=standard)

    if output_path:
        out_p = Path(output_path)
        if not out_p.is_absolute():
            out_p = Path(repo_root).resolve() / out_p
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(manifest.to_json(), encoding="utf-8")

    return manifest


def generate_file_proof(
    manifest_input: MerkleManifest | dict[str, Any],
    file_path: str,
) -> dict[str, Any]:
    """Emits an RFC 6962 inclusion proof verifying membership of a file in the Merkle tree."""
    data = manifest_input.to_dict() if isinstance(manifest_input, MerkleManifest) else manifest_input
    leaves = data.get("leaves", [])

    target_idx: int | None = None
    for idx, leaf in enumerate(leaves):
        entity_id = leaf.get("entity_id")
        path_in_data = leaf.get("data", {}).get("path")
        if entity_id == file_path or path_in_data == file_path:
            target_idx = idx
            break

    if target_idx is None:
        raise KeyError(f"File '{file_path}' not found in manifest leaves.")

    leaf_hashes = [l["leaf_hash"] for l in leaves]
    tree = MerkleTree(leaf_hashes)
    proof = tree.generate_proof(target_idx)
    target_leaf = leaves[target_idx]

    return {
        "file_path": file_path,
        "leaf_index": target_idx,
        "leaf_hash": target_leaf["leaf_hash"],
        "root_hash": data.get("root_hash", ""),
        "tree_size": len(leaves),
        "audit_path": [step.to_dict() for step in proof.audit_path],
    }


def verify_file_proof(proof: dict[str, Any], root_hash: str | None = None) -> bool:
    """Verifies that an inclusion proof reconstructs the expected Merkle root."""
    target_root = root_hash or proof.get("root_hash", "")
    inc_proof = MerkleInclusionProof.from_dict(proof)
    return verify_inclusion_proof(proof["leaf_hash"], inc_proof, target_root)


def verify_merkle_manifest(
    manifest_path: str | Path | dict[str, Any] | MerkleManifest,
    repo_root: str | Path = ".",
) -> MerkleVerificationResult:
    """Verifies compliance manifest internal integrity and detects modified, missing, or added files."""
    if isinstance(manifest_path, MerkleManifest):
        manifest_data = manifest_path.to_dict()
    elif isinstance(manifest_path, dict):
        manifest_data = manifest_path
    else:
        p = Path(manifest_path)
        if not p.is_file():
            return MerkleVerificationResult(
                ok=False,
                root_hash="",
                expected_root="",
                errors=[f"Manifest file not found: {p}"],
            )
        try:
            manifest_data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as exc:
            return MerkleVerificationResult(
                ok=False,
                root_hash="",
                expected_root="",
                errors=[f"Invalid manifest JSON: {exc}"],
            )

    expected_root = manifest_data.get("root_hash", "")
    leaves = manifest_data.get("leaves", [])
    leaf_hashes = [l.get("leaf_hash", "") for l in leaves]
    recomputed_root = MerkleTree(leaf_hashes).root_hash if leaf_hashes else EMPTY_ROOT_HASH

    errors: list[str] = []
    tampered_files: list[str] = []
    corrupted_id: str | None = None
    expected_hash: str | None = None
    computed_hash: str | None = None

    if recomputed_root != expected_root:
        errors.append(f"Root hash mismatch: expected {expected_root}, computed {recomputed_root}")

    repo_p = Path(repo_root).resolve()
    manifest_paths: set[str] = set()

    for leaf in leaves:
        rel = leaf.get("entity_id") or leaf.get("data", {}).get("path")
        if not rel:
            continue
        manifest_paths.add(rel)
        disk_file = repo_p / rel

        if not disk_file.is_file():
            tampered_files.append(rel)
            errors.append(f"File missing on disk: {rel}")
            if corrupted_id is None:
                corrupted_id = rel
            continue

        disk_bytes = disk_file.read_bytes()
        actual_sha256 = hashlib.sha256(disk_bytes).hexdigest()
        exp_sha256 = leaf.get("data", {}).get("sha256")

        if actual_sha256 != exp_sha256:
            tampered_files.append(rel)
            errors.append(f"Digest mismatch for '{rel}': expected {exp_sha256}, computed {actual_sha256}")
            if corrupted_id is None:
                corrupted_id = rel
                expected_hash = exp_sha256
                computed_hash = actual_sha256

        calc_leaf_hash = hash_leaf({"path": rel, "sha256": actual_sha256, "size": len(disk_bytes)})
        if calc_leaf_hash != leaf.get("leaf_hash"):
            if rel not in tampered_files:
                tampered_files.append(rel)
            errors.append(f"Leaf hash mismatch for '{rel}'")
            if corrupted_id is None:
                corrupted_id = rel

    # Check for untracked or unauthorized files added to target directories
    disk_artifacts = collect_project_artifacts(repo_p)
    for disk_rel in sorted(disk_artifacts.keys()):
        if disk_rel not in manifest_paths:
            tampered_files.append(disk_rel)
            errors.append(f"Untracked or unauthorized file detected: {disk_rel}")
            if corrupted_id is None:
                corrupted_id = disk_rel

    ok = len(tampered_files) == 0 and len(errors) == 0 and recomputed_root == expected_root
    return MerkleVerificationResult(
        ok=ok,
        root_hash=recomputed_root,
        expected_root=expected_root,
        artifacts_checked=len(leaves),
        tampered_files=tampered_files,
        errors=errors,
        corrupted_entity_id=corrupted_id,
        expected_hash=expected_hash,
        computed_hash=computed_hash,
    )
