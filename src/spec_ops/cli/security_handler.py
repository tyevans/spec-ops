"""CLI command handlers for security and queue operations."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from ..backlog.queue import BacklogQueue
from ..config.models import SpecOpsConfig
from ..security.audit import run_dependency_audit
from ..security.lockfile import verify_lockfile


def handle_audit_command(args: argparse.Namespace, config: SpecOpsConfig, parser: argparse.ArgumentParser) -> int:
    """Executes 'spec-ops audit dependencies' to scan CVEs and enforce license allowlists."""
    action = getattr(args, "audit_action", None)
    if action in ("dependencies", None):
        target = Path(getattr(args, "path", ".")).resolve()
        offline = getattr(args, "offline", False)
        report = run_dependency_audit(target, config=config, offline=offline)

        # Log active policy waivers applied
        for w in report.active_waivers_used:
            print(f"ℹ️ Active policy waiver '{w.id}' applied for package '{w.package}' (expires {w.expires})")

        # Report vulnerabilities
        for v in report.vulnerabilities:
            if v.waived:
                print(
                    f"ℹ️ Waived CVE advisory: {v.package} (version {v.version}) - {v.advisory_id} "
                    f"[Waiver: {v.waiver_id}, Expiration: {v.waiver_expires}]"
                )
            else:
                alias_str = f" ({', '.join(v.aliases)})" if v.aliases else ""
                print(
                    f"❌ Security Vulnerability Detected:\n"
                    f"   Package: {v.package} (version: {v.version})\n"
                    f"   Advisory ID: {v.advisory_id}{alias_str}\n"
                    f"   CVSS Score: {v.cvss_score}\n"
                    f"   Severity Level: {v.severity}\n"
                    f"   Minimum Remediating Version: {v.fixed_version}",
                    file=sys.stderr,
                )

        # Report license violations
        for lv in report.license_violations:
            if lv.waived:
                print(
                    f"ℹ️ Waived license violation: {lv.package} (version {lv.version}) - {lv.license} "
                    f"[Waiver: {lv.waiver_id}, Expiration: {lv.waiver_expires}]"
                )
            else:
                print(
                    f"❌ Open-Source Software License Violation:\n"
                    f"   Package: {lv.package} (version: {lv.version})\n"
                    f"   License: {lv.license}\n"
                    f"   Violation: {lv.reason}",
                    file=sys.stderr,
                )

        if not report.ok:
            print(
                f"❌ Audit Failed: {len(report.unwaived_vulnerabilities)} vulnerable package(s) "
                f"and {len(report.unwaived_license_violations)} license violation(s) identified.",
                file=sys.stderr,
            )
            return 1

        print("✅ Dependency audit passed: all dependencies satisfy vulnerability and license policies.")
        return 0

    parser.parse_args(["audit", "--help"])
    return 0


def handle_security_command(args: argparse.Namespace, config: SpecOpsConfig, parser: argparse.ArgumentParser) -> int:
    """Executes security subcommands including verify-lock."""
    if args.security_action == "verify-lock":
        target = Path(getattr(args, "path", ".")).resolve()
        ok, errors = verify_lockfile(target, run_uv=True)
        if not ok:
            print("❌ Supply-Chain Lockfile Verification Failed:", file=sys.stderr)
            for err in errors:
                print(f"   - {err}", file=sys.stderr)
            return 1
        print("✅ Lockfile verified: cryptographic hashes and package pins valid.")
        return 0

    parser.parse_args(["security", "--help"])
    return 0


def handle_queue_command(args: argparse.Namespace, config: SpecOpsConfig, parser: argparse.ArgumentParser) -> int:
    """Executes queue subcommands including gated task completion."""
    if args.queue_action == "complete":
        queue = BacklogQueue(config.backlog_dir)
        clean_id = args.task_id.upper()
        if not clean_id.startswith("TASK-") and clean_id.isdigit():
            clean_id = f"TASK-{clean_id.zfill(4)}"

        target_task = None
        for t in queue.list_all_tasks():
            if t.canonical_id == clean_id:
                target_task = t
                break

        if not target_task:
            print(f"❌ Task {args.task_id} not found in backlog.", file=sys.stderr)
            return 1

        base = getattr(args, "base", "main")
        ok, msg = queue.complete_task_with_gate(
            target_task, base_branch=base, repo_root=config.root_dir, config=config
        )
        if not ok:
            print(f"❌ {msg}", file=sys.stderr)
            print(msg)
            return 1
        print(f"✅ {msg}")
        return 0

    parser.parse_args(["queue", "--help"])
    return 0
