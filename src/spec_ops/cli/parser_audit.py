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

    p_audit_merkle = audit_subs.add_parser(
        "merkle",
        help="Compile, output, or verify tamper-evident Merkle compliance manifest for repository artifacts",
    )
    p_audit_merkle.add_argument(
        "--verify",
        metavar="VERIFY",
        default=None,
        help="Path to Merkle compliance manifest JSON to verify against repository artifacts",
    )
    p_audit_merkle.add_argument(
        "--output",
        metavar="OUTPUT",
        default=None,
        help="Output path for generated Merkle compliance manifest JSON",
    )
    p_audit_merkle.add_argument(
        "--json",
        action="store_true",
        help="Output Merkle manifest or verification result as JSON",
    )

    p_audit_sink = audit_subs.add_parser(
        "sink",
        help="Export structured event audit sink archive and historical streams",
    )
    p_audit_sink.add_argument(
        "--format",
        choices=["jsonl", "sqlite"],
        default="jsonl",
        help="Audit sink archive format (default: jsonl)",
    )
    p_audit_sink.add_argument(
        "--output",
        "-o",
        default=None,
        help="Output file path for exported audit sink archive",
    )
    p_audit_sink.add_argument(
        "--since",
        default=None,
        help="Filter events occurring on or after date/timestamp (ISO 8601 or YYYY-MM-DD)",
    )
    p_audit_sink.add_argument(
        "--until",
        default=None,
        help="Filter events occurring on or before date/timestamp",
    )
    p_audit_sink.add_argument(
        "--category",
        default=None,
        help="Filter events by category (e.g. security, worker, backlog)",
    )
    p_audit_sink.add_argument(
        "--aggregate-type",
        default=None,
        help="Filter events by aggregate type (e.g. Task, Worker, Security)",
    )
    p_audit_sink.add_argument(
        "--compress",
        action="store_true",
        help="Compress JSONL output with gzip",
    )
    p_audit_sink.add_argument(
        "--db",
        default=None,
        help="Path to SQLite event store (default: .specops/events.db)",
    )
    p_audit_sink.add_argument(
        "--json",
        action="store_true",
        help="Output execution summary as JSON",
    )

