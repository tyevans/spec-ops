"""Tamper-evident Merkle tree compliance data structures and audit manifest engine (ADR-0016).

This module re-exports core Merkle primitives, deliverable extraction, and verification
engines from spec_ops.security.audit for seamless backward compatibility.
"""

from __future__ import annotations

from .audit.exporter import (
    export_compliance_manifest,
    extract_repo_compliance_deliverables,
)
from .audit.merkle import (
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
from .audit.verifier import (
    VerificationResult,
    verify_audit_trail,
    verify_compliance_manifest,
)

__all__ = [
    "ComplianceDeliverable",
    "ComplianceManifest",
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
    "verify_audit_trail",
    "verify_compliance_manifest",
    "verify_inclusion_proof",
]
