"""Subparser registration helpers for audit commands."""

from __future__ import annotations

import argparse


def register_audit_subparsers(subparsers: argparse._SubParsersAction) -> None:
    """Registers audit commands (dependencies, export, verify, provenance, proof, verify-proof)."""
    p_audit_cmd = subparsers.add_parser("audit", help="Audit project dependencies, compliance manifests, and security policies")
    audit_subs = p_audit_cmd.add_subparsers(dest="audit_action", help="Audit action")
    p_audit_deps = audit_subs.add_parser("dependencies", help="Scan dependencies for CVEs and license allowlist compliance")
    p_audit_deps.add_argument("--path", default=".", help="Directory containing dependencies (default: current directory)")
    p_audit_deps.add_argument("--offline", action="store_true", help="Run in air-gapped/offline mode with local cache")

    p_audit_export = audit_subs.add_parser("export", help="Compile and export tamper-evident Merkle compliance audit manifest")
    p_audit_export.add_argument("--standard", default="soc2", help="Compliance standard profile (e.g. soc2, iso27001, hipaa)")
    p_audit_export.add_argument("--output", default="dist/compliance/", help="Output directory for compliance manifest and root hash")

    p_audit_verify = audit_subs.add_parser("verify", help="Verify cryptographic compliance manifest integrity and SDLC traceability")
    p_audit_verify.add_argument("--manifest", default="dist/compliance/soc2-audit-manifest.json", help="Path to compliance manifest JSON")
    p_audit_verify.add_argument("--repo", default=".", help="Path to repository root (default: current directory)")

    p_audit_prov = audit_subs.add_parser(
        "provenance",
        aliases=["traceability"],
        help="Audit unbroken commit trailers, SDLC traceability lineage, and contributor provenance",
    )
    p_audit_prov.add_argument("--strict", action="store_true", help="Fail with exit code 1 if any unanchored commits, orphaned tasks, or missing tasks exist")
    p_audit_prov.add_argument("--contributions", action="store_true", help="Break down delivered tasks and merged commits by contributor provenance")
    p_audit_prov.add_argument("--repo", default=".", help="Repository root path (default: current directory)")

    p_audit_proof = audit_subs.add_parser(
        "proof",
        help="Generate self-contained Merkle inclusion proof for a single deliverable",
    )
    p_audit_proof.add_argument("--deliverable", required=True, help="Target deliverable or task canonical ID (e.g. TASK-0030)")
    p_audit_proof.add_argument("--manifest", default="dist/compliance/soc2-audit-manifest.json", help="Path to compliance manifest JSON")
    p_audit_proof.add_argument("--out", default=None, help="Output file path to save proof JSON")
    p_audit_proof.add_argument("--json", action="store_true", help="Output proof JSON to stdout")

    p_audit_vproof = audit_subs.add_parser(
        "verify-proof",
        help="Verify Merkle inclusion proof against trusted root in offline execution",
    )
    p_audit_vproof.add_argument("proof_file", help="Path to inclusion proof JSON file")
    p_audit_vproof.add_argument("--root", required=True, help="Trusted Merkle root hash for verification")
    p_audit_vproof.add_argument("--json", action="store_true", help="Output verification result as JSON")
