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
    """Executes 'spec-ops audit' commands (export, verify, dependencies, provenance)."""
    action = getattr(args, "audit_action", None)

    if action in ("provenance", "traceability"):
        from ..core.provenance import run_provenance_audit

        return run_provenance_audit(args, config)

    if action == "export":
        from ..security.audit.exporter import export_compliance_manifest

        standard = getattr(args, "standard", "soc2")
        out_dir = getattr(args, "output", "dist/compliance/")
        manifest_file, root_file, manifest = export_compliance_manifest(
            repo_dir=config.root_dir,
            standard=standard,
            output_dir=out_dir,
        )
        print(f"✨ Compiled compliance audit manifest: {manifest_file}")
        print(f"✨ Generated top-level Merkle root: {root_file}")
        print(f"   Standard:     {manifest.standard.upper()}")
        print(f"   Deliverables: {manifest.tree_size}")
        print(f"   Merkle Root:  {manifest.root_hash}")
        return 0

    if action == "verify":
        from ..security.audit.verifier import verify_audit_trail

        manifest_arg = getattr(args, "manifest", "dist/compliance/soc2-audit-manifest.json")
        repo_arg = getattr(args, "repo", ".")
        manifest_path = Path(manifest_arg)
        if not manifest_path.is_absolute():
            manifest_path = config.root_dir / manifest_path

        repo_path = Path(repo_arg)
        if not repo_path.is_absolute():
            repo_path = config.root_dir / repo_path

        if not manifest_path.is_file():
            print(f"❌ Manifest file not found: {manifest_path}", file=sys.stderr)
            print(f"❌ Manifest file not found: {manifest_path}")
            return 1

        result = verify_audit_trail(manifest_path=manifest_path, repo_dir=repo_path)
        if not result.ok:
            error_output = [
                "❌ Compliance Verification Failed: Deliverable integrity violation detected."
            ]
            if result.corrupted_entity_id:
                error_output.append(f"   Corrupted Task ID: {result.corrupted_entity_id}")
                error_output.append(f"   Expected SHA-256:  {result.expected_hash}")
                error_output.append(f"   Computed SHA-256:  {result.computed_hash}")
            for err in result.errors:
                error_output.append(f"   - {err}")

            full_msg = "\n".join(error_output)
            print(full_msg, file=sys.stderr)
            print(full_msg)
            return 1

        print("✅ Compliance Audit Verification PASSED:")
        print(f"   Manifest:     {manifest_path}")
        print(f"   Deliverables: {result.deliverables_checked}")
        print(f"   Merkle Root:  {result.root_hash}")
        return 0

    if action == "proof":
        from ..security.audit.proof_cli import handle_audit_proof

        return handle_audit_proof(args, config)

    if action == "verify-proof":
        from ..security.audit.proof_cli import handle_audit_verify_proof

        return handle_audit_verify_proof(args, config)

    if action == "merkle":
        import json
        from ..security.merkle_manifest import (
            generate_merkle_manifest,
            verify_merkle_manifest,
        )

        verify_target = getattr(args, "verify", None)
        as_json = bool(getattr(args, "json", False))
        out_target = getattr(args, "output", None)
        repo_target = config.root_dir

        if verify_target:
            manifest_p = Path(verify_target)
            if not manifest_p.is_absolute():
                manifest_p = repo_target / manifest_p

            result = verify_merkle_manifest(manifest_path=manifest_p, repo_root=repo_target)
            if as_json:
                print(json.dumps(result.to_dict(), indent=2))
                return 0 if result.ok else 1

            if not result.ok:
                print("❌ Merkle compliance verification failed: digest mismatch detected.", file=sys.stderr)
                for f in result.tampered_files:
                    print(f"   Tampered file: {f}", file=sys.stderr)
                for err in result.errors:
                    print(f"   - {err}", file=sys.stderr)
                return 1

            print("✅ Merkle Compliance Manifest PASSED: all artifacts verified.")
            print(f"   Manifest:     {manifest_p}")
            print(f"   Merkle Root:  {result.root_hash}")
            print(f"   Artifacts:    {result.artifacts_checked}")
            return 0

        manifest = generate_merkle_manifest(repo_root=repo_target, output_path=out_target)
        if as_json:
            print(manifest.to_json())
            return 0

        print("✨ Generated Merkle compliance manifest:")
        print(f"   Merkle Root:  {manifest.root_hash}")
        print(f"   Artifacts:    {manifest.tree_size}")
        if out_target:
            print(f"   Manifest:     {out_target}")
        return 0

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

    if args.security_action == "sentinel":
        import json
        from ..security.lockfile_sentinel import inspect_lockfile_sentinel

        target = Path(getattr(args, "path", ".")).resolve()
        fix = bool(getattr(args, "fix", False))
        as_json = bool(getattr(args, "json", False))

        result = inspect_lockfile_sentinel(target, fix=fix, config=config)

        if as_json:
            print(json.dumps(result.to_dict(), indent=2))
            return 0 if result.ok else 1

        if not result.ok:
            print("❌ Supply-Chain Lockfile Mutation Sentinel Violation:", file=sys.stderr)
            for err in result.violations:
                print(f"   - {err}", file=sys.stderr)
            return 1

        if result.waiver_applied:
            print(f"ℹ️ Lockfile mutation authorized by waiver: {result.waiver_details}")
        elif result.remediated:
            print(f"✅ Remediated unauthorized lockfile modification(s): {', '.join(result.remediated)}")
        else:
            print("✅ Lockfile Sentinel passed: zero unauthorized lockfile mutations detected.")
        return 0

    if args.security_action == "audit-lockfile":
        from ..security.supply_chain_daemon import handle_audit_lockfile

        return handle_audit_lockfile(args, config)

    if args.security_action == "scan":
        import json
        from ..security.entropy_plugins import (
            EntropyScannerConfig,
            ShannonEntropyScanner,
        )

        target_arg = getattr(args, "path", ".")
        target_path = Path(target_arg)
        if not target_path.is_absolute():
            if (config.root_dir / target_arg).exists():
                target_path = (config.root_dir / target_arg).resolve()
            else:
                target_path = target_path.resolve()

        threshold = float(getattr(args, "threshold", 4.5))
        as_json = bool(getattr(args, "json", False))

        cfg_dir = target_path if target_path.is_dir() else target_path.parent
        scanner_config = EntropyScannerConfig.load_from_project(cfg_dir)
        if getattr(args, "threshold", None) is not None:
            for r in scanner_config.rules:
                r.threshold = threshold

        scanner = ShannonEntropyScanner(scanner_config)
        findings = scanner.scan_file(target_path) if target_path.is_file() else scanner.scan_directory(target_path)

        if as_json:
            result = {
                "is_clean": len(findings) == 0,
                "findings_count": len(findings),
                "findings": [f.to_dict() for f in findings],
            }
            print(json.dumps(result, indent=2))
            return 0 if len(findings) == 0 else 1

        if findings:
            print(f"❌ Security violation: {len(findings)} credential leak risk(s) detected:", file=sys.stderr)
            for f in findings:
                print(f"   [{f.rule_name}] {f.file_path}:{f.line_number}: {f.reason} (token: {f.masked_token})", file=sys.stderr)
            return 1

        print("✅ Security Invariant Met: 0 credential leaks detected.")
        return 0

    if args.security_action == "scan-secrets":
        import json
        from ..security.secrets.scanner import scan_file, scan_worktree

        target = Path(getattr(args, "path", ".")).resolve()
        staged = bool(getattr(args, "staged", False))
        threshold = float(getattr(args, "threshold", 3.7))
        as_json = bool(getattr(args, "json", False))

        if target.is_file():
            report = scan_file(target, threshold=threshold)
        else:
            report = scan_worktree(target, staged_only=staged, threshold=threshold)

        if as_json:
            print(json.dumps(report.to_dict(), indent=2))
            return 0 if report.is_clean else 1

        if not report.is_clean:
            print(report.format_diagnostics(), file=sys.stderr)
            return 1

        scope = "staged changes" if staged else "working tree"
        print(f"✅ Security Invariant Met: 0 credential leaks detected in {scope}.")
        return 0

    if args.security_action == "hook":
        from ..security.git_hooks import (
            install_hook,
            run_hook_sentinel,
            uninstall_hook,
            verify_hook,
        )

        target = Path(getattr(args, "path", ".")).resolve()
        action = getattr(args, "hook_action", None)

        if action == "install":
            ok, hook_path, msg = install_hook(target, force=bool(getattr(args, "force", False)))
            if ok:
                print(f"✅ {msg}")
                return 0
            print(f"❌ {msg}", file=sys.stderr)
            return 1

        if action == "uninstall":
            ok, hook_path, msg = uninstall_hook(target)
            if ok:
                print(f"✅ {msg}")
                return 0
            print(f"❌ {msg}", file=sys.stderr)
            return 1

        if action == "verify":
            ok, msg = verify_hook(target)
            if ok:
                print(f"✅ {msg}")
                return 0
            print(f"❌ {msg}", file=sys.stderr)
            return 1

        if action == "run":
            result = run_hook_sentinel(target, config=config)
            if result.ok:
                print(f"✅ Pre-commit Sentinel Passed: 0 violations across {result.staged_files_count} staged file(s).")
                return 0
            print("❌ Pre-commit Sentinel Violation (commit aborted):", file=sys.stderr)
            for err in result.violations:
                print(f"   - {err}", file=sys.stderr)
            return 1

        parser.parse_args(["security", "hook", "--help"])
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
