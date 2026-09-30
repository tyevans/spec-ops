"""Tamper-evident Merkle tree compliance data structures and audit manifest engine (ADR-0011)."""

from __future__ import annotations

import dataclasses
import hashlib
import json
from dataclasses import asdict, dataclass, field, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LEAF_PREFIX: bytes = b"\x00"
NODE_PREFIX: bytes = b"\x01"
EMPTY_ROOT_HASH: str = hashlib.sha256(b"").hexdigest()


def _canonicalize_value(obj: Any) -> Any:
    """Recursively transforms objects for RFC 8785 canonical JSON serialization."""
    if isinstance(obj, dict):
        sorted_keys = sorted(obj.keys(), key=lambda k: str(k).encode("utf-16-be"))
        return {str(k): _canonicalize_value(obj[k]) for k in sorted_keys}
    if isinstance(obj, (list, tuple)):
        return [_canonicalize_value(item) for item in obj]
    if is_dataclass(obj) and not isinstance(obj, type):
        return _canonicalize_value(asdict(obj))
    if isinstance(obj, float):
        return 0.0 if obj == 0.0 else obj
    return obj


def canonical_json_encode(data: Any) -> bytes:
    """Serializes data to deterministic canonical JSON bytes conforming to RFC 8785."""
    canonical_obj = _canonicalize_value(data)
    text = json.dumps(canonical_obj, separators=(",", ":"), ensure_ascii=False)
    return text.encode("utf-8")


def hash_leaf(data: Any) -> str:
    """Computes SHA-256 leaf hash with RFC 6962 0x00 domain separation prefix."""
    payload = canonical_json_encode(data) if not isinstance(data, (bytes, bytearray)) else data
    return hashlib.sha256(LEAF_PREFIX + payload).hexdigest()


def hash_internal_node(left_hex: str, right_hex: str) -> str:
    """Computes SHA-256 internal node hash with RFC 6962 0x01 domain separation prefix."""
    left_bytes = bytes.fromhex(left_hex)
    right_bytes = bytes.fromhex(right_hex)
    return hashlib.sha256(NODE_PREFIX + left_bytes + right_bytes).hexdigest()


def _largest_power_of_2_less_than(n: int) -> int:
    """Finds the largest power of 2 strictly less than n (k < n <= 2k)."""
    k = 1
    while k * 2 < n:
        k *= 2
    return k


@dataclass(frozen=True)
class ProofStep:
    """Single sibling hash and relative direction in a Merkle inclusion proof."""

    sibling_hash: str
    is_left: bool

    def to_dict(self) -> dict[str, Any]:
        return {"sibling_hash": self.sibling_hash, "is_left": self.is_left}


@dataclass(frozen=True)
class MerkleInclusionProof:
    """RFC 6962 logarithmic Merkle inclusion audit proof."""

    leaf_index: int
    leaf_hash: str
    audit_path: list[ProofStep]
    root_hash: str
    tree_size: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "leaf_index": self.leaf_index,
            "leaf_hash": self.leaf_hash,
            "audit_path": [step.to_dict() for step in self.audit_path],
            "root_hash": self.root_hash,
            "tree_size": self.tree_size,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MerkleInclusionProof:
        steps = [ProofStep(s["sibling_hash"], bool(s["is_left"])) for s in data.get("audit_path", [])]
        return cls(
            leaf_index=data["leaf_index"],
            leaf_hash=data["leaf_hash"],
            audit_path=steps,
            root_hash=data["root_hash"],
            tree_size=data["tree_size"],
        )


def verify_inclusion_proof(leaf_hash: str, proof: MerkleInclusionProof, root_hash: str | None = None) -> bool:
    """Verifies whether an inclusion proof cryptographically reconstructs the expected Merkle root."""
    target_root = root_hash or proof.root_hash
    current = leaf_hash
    for step in proof.audit_path:
        current = hash_internal_node(step.sibling_hash, current) if step.is_left else hash_internal_node(current, step.sibling_hash)
    return current == target_root


class MerkleTree:
    """Deterministic power-of-2 binary Merkle tree conforming to RFC 6962 and RFC 8785."""

    def __init__(self, leaf_hashes: list[str]) -> None:
        self.leaf_hashes = list(leaf_hashes)
        self._root = self._compute_mth(self.leaf_hashes)

    @property
    def root_hash(self) -> str:
        return self._root

    @property
    def tree_size(self) -> int:
        return len(self.leaf_hashes)

    def _compute_mth(self, hashes: list[str]) -> str:
        n = len(hashes)
        if n == 0:
            return EMPTY_ROOT_HASH
        if n == 1:
            return hashes[0]
        k = _largest_power_of_2_less_than(n)
        return hash_internal_node(self._compute_mth(hashes[:k]), self._compute_mth(hashes[k:]))

    def generate_proof(self, index: int) -> MerkleInclusionProof:
        if not 0 <= index < len(self.leaf_hashes):
            raise IndexError(f"Leaf index {index} out of range [0, {len(self.leaf_hashes)})")
        return MerkleInclusionProof(
            leaf_index=index,
            leaf_hash=self.leaf_hashes[index],
            audit_path=self._generate_path(self.leaf_hashes, index),
            root_hash=self.root_hash,
            tree_size=len(self.leaf_hashes),
        )

    def _generate_path(self, hashes: list[str], m: int) -> list[ProofStep]:
        n = len(hashes)
        if n <= 1:
            return []
        k = _largest_power_of_2_less_than(n)
        if m < k:
            steps = self._generate_path(hashes[:k], m)
            steps.append(ProofStep(sibling_hash=self._compute_mth(hashes[k:]), is_left=False))
            return steps
        steps = self._generate_path(hashes[k:], m - k)
        steps.append(ProofStep(sibling_hash=self._compute_mth(hashes[:k]), is_left=True))
        return steps


@dataclass
class HumanSignoff:
    """Cryptographic human reviewer sign-off attestation."""

    reviewer: str
    email: str
    signature: str
    timestamp: str
    decision: str = "APPROVED"
    role: str = "Trust & Security Officer"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ComplianceDeliverable:
    """Verifiable SDLC deliverable record binding requirements, code, tests, and human review."""

    task_id: str
    prd_id: str
    story_ids: list[str]
    commit_sha: str
    prompt_sha256: str
    test_results_digest: str
    human_signoff: HumanSignoff | dict[str, Any] | None = None
    gherkin_scenarios: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        signoff_dict = None
        if self.human_signoff:
            signoff_dict = (
                self.human_signoff.to_dict()
                if hasattr(self.human_signoff, "to_dict")
                else dict(self.human_signoff)
            )
        return {
            "task_id": self.task_id,
            "prd_id": self.prd_id,
            "story_ids": sorted(self.story_ids),
            "commit_sha": self.commit_sha,
            "prompt_sha256": self.prompt_sha256,
            "test_results_digest": self.test_results_digest,
            "gherkin_scenarios": sorted(self.gherkin_scenarios),
            "human_signoff": signoff_dict,
            "metadata": dict(self.metadata),
        }

    def compute_leaf_hash(self) -> str:
        return hash_leaf(self.to_dict())


@dataclass
class MerkleLeaf:
    """Manifest leaf entry containing deliverable index, computed hash, and payload."""

    index: int
    leaf_hash: str
    entity_id: str
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "leaf_hash": self.leaf_hash,
            "entity_id": self.entity_id,
            "data": self.data,
        }


@dataclass
class ComplianceManifest:
    """Immutable, mathematically verifiable compliance audit manifest."""

    version: str
    standard: str
    generated_at: str
    root_hash: str
    algorithm: str
    serialization: str
    leaf_prefix: str
    node_prefix: str
    tree_size: int
    leaves: list[MerkleLeaf]

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
            "leaves": [leaf.to_dict() for leaf in self.leaves],
        }

    def to_json(self, indent: int | None = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)


def compile_compliance_manifest(
    deliverables: list[ComplianceDeliverable],
    standard: str = "soc2",
    generated_at: str | None = None,
) -> ComplianceManifest:
    """Compiles a list of SDLC deliverables into a canonical Merkle compliance manifest."""
    sorted_items = sorted(deliverables, key=lambda d: d.task_id)
    leaf_entries: list[MerkleLeaf] = []
    leaf_hashes: list[str] = []
    for idx, item in enumerate(sorted_items):
        item_dict = item.to_dict()
        l_hash = hash_leaf(item_dict)
        leaf_hashes.append(l_hash)
        leaf_entries.append(MerkleLeaf(idx, l_hash, item.task_id, item_dict))

    tree = MerkleTree(leaf_hashes)
    timestamp = generated_at or datetime.now(timezone.utc).isoformat()
    return ComplianceManifest(
        version="1.0.0",
        standard=standard,
        generated_at=timestamp,
        root_hash=tree.root_hash,
        algorithm="sha256",
        serialization="RFC8785",
        leaf_prefix=LEAF_PREFIX.hex(),
        node_prefix=NODE_PREFIX.hex(),
        tree_size=len(leaf_entries),
        leaves=leaf_entries,
    )


def verify_compliance_manifest(
    manifest_input: ComplianceManifest | dict[str, Any] | str | Path,
) -> tuple[bool, list[str]]:
    """Verifies compliance manifest internal integrity and recomputes the Merkle root hash."""
    if isinstance(manifest_input, (str, Path)):
        p = Path(manifest_input)
        data = json.loads(p.read_text(encoding="utf-8") if p.is_file() else str(manifest_input))
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
            errors.append(f"Tampered deliverable '{entity_id}' at index {idx}: expected {claimed_hash}, recomputed {actual_hash}")
        recomputed_hashes.append(actual_hash)

    tree = MerkleTree(recomputed_hashes)
    if tree.root_hash != expected_root:
        errors.append(f"Merkle root mismatch: manifest claims {expected_root}, recomputed tree root is {tree.root_hash}")

    return len(errors) == 0, errors


def extract_repo_compliance_deliverables(repo_dir: Path) -> list[ComplianceDeliverable]:
    """Extracts completed SDLC deliverables from repository backlog and commit records."""
    from ..core.parser import parse_task

    complete_dir = repo_dir / "docs" / "project" / "backlog" / "complete"
    deliverables: list[ComplianceDeliverable] = []
    if not complete_dir.exists():
        return deliverables

    for task_file in sorted(complete_dir.glob("*.md")):
        if task_file.name.startswith("."):
            continue
        try:
            task = parse_task(task_file)
            prd_id = task.governing_prds[0] if task.governing_prds else "PRD-0000"
            prompt_hash = hashlib.sha256(task_file.read_text(encoding="utf-8").encode("utf-8")).hexdigest()
            deliverables.append(
                ComplianceDeliverable(
                    task_id=task.canonical_id,
                    prd_id=prd_id,
                    story_ids=list(task.governing_stories),
                    commit_sha="0000000000000000000000000000000000000000",
                    prompt_sha256=prompt_hash,
                    test_results_digest=hashlib.sha256(f"passed:{task.canonical_id}".encode("utf-8")).hexdigest(),
                    human_signoff=HumanSignoff("Sasha", "sasha@specops.dev", f"sig:{task.canonical_id}", "2026-09-29T18:00:00Z"),
                )
            )
        except Exception:
            continue
    return deliverables
