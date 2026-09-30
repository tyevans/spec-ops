"""Tamper-evident Merkle compliance manifests, deliverable export, and verification engine (ADR-0016)."""

from __future__ import annotations

from .dependency import DependencyAuditReport, run_dependency_audit
from .exporter import export_compliance_manifest, extract_repo_compliance_deliverables
from .merkle import (
    EMPTY_ROOT_HASH,
    LEAF_PREFIX,
    NODE_PREFIX,
    ComplianceDeliverable,
    ComplianceManifest,
    HumanSignoff,
    MerkleInclusionProof,
    MerkleLeaf,
    MerkleTree,
    ProofStep,
    canonical_json_encode,
    compile_compliance_manifest,
    hash_internal_node,
    hash_leaf,
    verify_inclusion_proof,
)
from .verifier import VerificationResult, verify_audit_trail, verify_compliance_manifest

__all__ = [
    "ComplianceDeliverable",
    "ComplianceManifest",
    "DependencyAuditReport",
    "EMPTY_ROOT_HASH",
    "HumanSignoff",
    "LEAF_PREFIX",
    "MerkleInclusionProof",
    "MerkleLeaf",
    "MerkleTree",
    "NODE_PREFIX",
    "ProofStep",
    "VerificationResult",
    "canonical_json_encode",
    "compile_compliance_manifest",
    "export_compliance_manifest",
    "extract_repo_compliance_deliverables",
    "hash_internal_node",
    "hash_leaf",
    "run_dependency_audit",
    "verify_audit_trail",
    "verify_compliance_manifest",
    "verify_inclusion_proof",
]
