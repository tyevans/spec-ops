"""Customer UAT receipt generation, verification, and CLI dispatching per ADR-0014."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.parser import SpecOpsParser
from .manifest import compute_git_tree_digest, verify_release_manifest
from .uat import (
    harvest_uat_readiness,
    load_uat_signoffs,
    record_uat_signoff,
)
from .uat_receipt import serialize_canonical_json


def compute_uat_receipt_signature(
    prd_id: str,
    tree_digest: str,
    test_correlation: list[dict[str, Any]],
    uat_summary: dict[str, Any],
) -> str:
    """Computes deterministic SHA-256 signature sealing receipt fields together."""
    payload = (
        f"PRD:{prd_id}\n"
        f"TREE:{tree_digest}\n"
        f"TESTS:{serialize_canonical_json(test_correlation)}"
        f"UAT:{serialize_canonical_json(uat_summary)}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def generate_customer_uat_receipt(
    repo_root: Path | str,
    prd_id: str | None = None,
    output_path: Path | str | None = None,
    allow_uncommitted: bool = False,
) -> dict[str, Any]:
    """Generates a tamper-evident, cryptographic Customer UAT receipt with git tree digest."""
    root = Path(repo_root).resolve()
    docs_dir = root / "docs" / "project"
    parser = SpecOpsParser(docs_dir)
    p_data = parser.parse_all()

    # Determine target PRD
    target_prd = None
    if prd_id:
        num_m = re.search(r"\d+", prd_id)
        target_clean = f"PRD-{num_m.group(0).zfill(4)}" if num_m else prd_id.strip().upper()
        for p in p_data.prds:
            c_p = f"PRD-{re.search(r'\d+', p.id).group(0).zfill(4)}" if re.search(r"\d+", p.id) else p.id
            if c_p == target_clean:
                target_prd = p
                break
        if not target_prd:
            target_prd_id = target_clean
            target_prd_title = target_clean
        else:
            target_prd_id = f"PRD-{re.search(r'\d+', target_prd.id).group(0).zfill(4)}" if re.search(r'\d+', target_prd.id) else target_prd.id
            target_prd_title = target_prd.title
    else:
        # Fall back to first accepted PRD or first available PRD
        accepted = [p for p in p_data.prds if p.status.lower() == "accepted"]
        candidate = accepted[0] if accepted else (p_data.prds[0] if p_data.prds else None)
        if not candidate:
            raise ValueError("No PRDs found in project to generate UAT receipt.")
        target_prd = candidate
        target_prd_id = f"PRD-{re.search(r'\d+', candidate.id).group(0).zfill(4)}" if re.search(r'\d+', candidate.id) else candidate.id
        target_prd_title = candidate.title

    tree_digest, clean, errs = compute_git_tree_digest(root, allow_uncommitted=allow_uncommitted)
    if errs:
        raise ValueError(f"Cannot generate UAT receipt: {'; '.join(errs)}")

    harvest = harvest_uat_readiness(root, target_prd_id=target_prd_id)
    matrix = harvest.get("matrix", [])

    total_outcomes = len(matrix)
    approved_outcomes = sum(1 for m in matrix if m.get("uat_status") == "Approved")
    passed_tests = sum(1 for m in matrix if m.get("test_status") == "Passed (CI)")

    test_status = "Passed (CI)" if (passed_tests == total_outcomes and total_outcomes > 0) else "Pending (CI)"
    test_summary = {
        "status": test_status,
        "total_outcomes": total_outcomes,
        "passed_outcomes": passed_tests,
    }

    uat_status = "Approved" if (approved_outcomes == total_outcomes and total_outcomes > 0) else "Pending PM"
    uat_summary = {
        "status": uat_status,
        "total_outcomes": total_outcomes,
        "approved_outcomes": approved_outcomes,
    }

    signature = compute_uat_receipt_signature(
        prd_id=target_prd_id,
        tree_digest=tree_digest,
        test_correlation=matrix,
        uat_summary=uat_summary,
    )

    receipt_data: dict[str, Any] = {
        "$schema": "spec-ops/uat-receipt-v1",
        "version": "1.0",
        "prd": {
            "id": target_prd_id,
            "title": target_prd_title,
        },
        "verified_tree_digest": tree_digest,
        "test_correlation": matrix,
        "test_verification": test_summary,
        "uat_verification": uat_summary,
        "receipt_signature": signature,
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }

    if output_path:
        out_file = Path(output_path).resolve()
    else:
        out_file = root / "dist" / "uat" / f"{target_prd_id}-uat-receipt.json"

    out_file.parent.mkdir(parents=True, exist_ok=True)
    out_file.write_text(serialize_canonical_json(receipt_data), encoding="utf-8")

    return receipt_data


def verify_customer_uat_receipt(
    receipt: dict[str, Any] | Path | str,
    repo_root: Path | str,
) -> tuple[bool, list[str]]:
    """Headless verification of Customer UAT receipt signature and git tree digest in <50ms."""
    violations: list[str] = []
    root = Path(repo_root).resolve()

    if isinstance(receipt, (str, Path)):
        p = Path(receipt).resolve()
        if not p.is_file():
            return False, [f"Receipt file does not exist: {p}"]
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except Exception as e:
            return False, [f"Malformed receipt JSON: {e}"]
    elif isinstance(receipt, dict):
        data = receipt
    else:
        return False, ["Receipt must be a dict or file path."]

    # If it's a release manifest, delegate to release manifest verifier
    if data.get("$schema") == "spec-ops/release-manifest-v1" or "manifest_signature" in data:
        return verify_release_manifest(data, root)

    # 1. Structural schema verification
    required_keys = [
        "prd",
        "verified_tree_digest",
        "test_correlation",
        "uat_verification",
        "receipt_signature",
    ]
    for rk in required_keys:
        if rk not in data:
            violations.append(f"Missing required receipt field: '{rk}'.")

    if violations:
        return False, violations

    prd = data["prd"]
    prd_id = prd.get("id", "")
    tree_digest = data["verified_tree_digest"]
    test_correlation = data["test_correlation"]
    uat_summary = data["uat_verification"]
    receipt_signature = data["receipt_signature"]

    # 2. Cryptographic signature check
    expected_sig = compute_uat_receipt_signature(
        prd_id=prd_id,
        tree_digest=tree_digest,
        test_correlation=test_correlation,
        uat_summary=uat_summary,
    )
    if expected_sig != receipt_signature:
        violations.append(
            f"Cryptographic signature invalid: expected {expected_sig[:12]}..., got {receipt_signature[:12]}..."
        )

    # 3. Git tree SHA-256 integrity check
    curr_tree, clean, errs = compute_git_tree_digest(root, allow_uncommitted=False)
    if errs:
        violations.extend(errs)
    elif curr_tree != tree_digest:
        violations.append(
            f"Tampering detected: repository tree SHA-256 ({curr_tree[:12]}...) does not match receipt ({tree_digest[:12]}...)."
        )

    # 4. UAT approval status
    if uat_summary.get("status") != "Approved":
        violations.append(
            f"UAT sign-off failure: status is '{uat_summary.get('status')}'; mandatory PM UAT approval required."
        )

    return len(violations) == 0, violations


def handle_uat_status(config: SpecOpsConfig, json_output: bool = False) -> int:
    """CLI handler for 'spec-ops prd uat status [--json]'."""
    harvest = harvest_uat_readiness(config.root_dir)
    if json_output:
        print(serialize_canonical_json(harvest).strip())
        return 0

    readiness = harvest.get("readiness_percentage", 0.0)
    matrix = harvest.get("matrix", [])

    print("=== Customer UAT Readiness Matrix ===")
    print(f"Overall Delivery Readiness: {readiness:.1f}%\n")

    if not matrix:
        print("No checkable outcomes found in accepted PRDs.")
        return 0

    header = f"{'PRD Outcome':<45} | {'Linked Story':<14} | {'Test Status':<12} | {'UAT Status':<14} | {'Reviewer'}"
    print(header)
    print("-" * len(header))

    for item in matrix:
        outcome_desc = f"{item['prd_id']} Outcome {item['outcome_id']}: {item['outcome_text']}"
        if len(outcome_desc) > 43:
            outcome_desc = outcome_desc[:40] + "..."
        stories = ", ".join(item.get("linked_stories", [])) or "-"
        test_st = item.get("test_status", "Pending (CI)")
        uat_st = item.get("uat_status", "Pending PM")
        reviewer = item.get("reviewer", "")

        print(f"{outcome_desc:<45} | {stories:<14} | {test_st:<12} | {uat_st:<14} | {reviewer}")

    return 0


def handle_uat_sign(
    config: SpecOpsConfig,
    prd: str,
    outcome: str,
    reviewer: str,
    status: str = "Approved",
    notes: str = "",
) -> int:
    """CLI handler for 'spec-ops prd uat sign'."""
    try:
        entry = record_uat_signoff(
            repo_root=config.root_dir,
            prd_id=prd,
            outcome_id=outcome,
            reviewer=reviewer,
            status=status,
            notes=notes,
        )
        print(f"✅ Recorded PM business acceptance sign-off for {entry.get('prd_id', prd)} Outcome {entry.get('outcome_id', outcome)}: {entry.get('status', status)}")
        print(f"   Reviewer: {entry.get('reviewer', reviewer)}")
        if entry.get("notes"):
            print(f"   Notes: {entry.get('notes')}")
        return 0
    except Exception as exc:
        print(f"❌ Failed to record UAT sign-off: {exc}")
        return 1


def handle_uat_receipt(
    config: SpecOpsConfig,
    prd: str | None = None,
    out: str | None = None,
    verify: bool = False,
) -> int:
    """CLI handler for 'spec-ops prd uat receipt [--prd PRD] [--out OUT] [--verify]'."""
    if verify:
        target_path: Path | None = None
        if out:
            target_path = Path(out).resolve()
        elif prd:
            num_m = re.search(r"\d+", prd)
            c_prd = f"PRD-{num_m.group(0).zfill(4)}" if num_m else prd.strip().upper()
            candidates = [
                config.root_dir / "dist" / "uat" / f"{c_prd}-uat-receipt.json",
                config.root_dir / "dist" / "releases" / f"{c_prd}-release-manifest.json",
            ]
            for c in candidates:
                if c.is_file():
                    target_path = c
                    break
            if not target_path:
                target_path = candidates[0]
        else:
            candidates = list((config.root_dir / "dist" / "uat").glob("*.json")) + list(
                (config.root_dir / "dist" / "releases").glob("*.json")
            )
            if candidates:
                target_path = candidates[0]

        if not target_path or not target_path.is_file():
            print(f"❌ Receipt file does not exist: {target_path or 'No path specified'}")
            return 1

        valid, issues = verify_customer_uat_receipt(target_path, config.root_dir)
        if valid:
            print(f"✅ Cryptographic Customer UAT receipt verified successfully: {target_path.name}")
            return 0
        else:
            print(f"❌ Cryptographic Customer UAT receipt verification failed: {target_path.name}")
            for iss in issues:
                print(f"   - {iss}")
            return 1

    # Generation mode
    try:
        receipt = generate_customer_uat_receipt(
            repo_root=config.root_dir,
            prd_id=prd,
            output_path=out,
            allow_uncommitted=True,
        )
        out_p = (
            Path(out).resolve()
            if out
            else config.root_dir / "dist" / "uat" / f"{receipt['prd']['id']}-uat-receipt.json"
        )
        print(f"✅ Generated cryptographic Customer UAT receipt for {receipt['prd']['id']}")
        print(f"   Receipt Path: {out_p}")
        print(f"   Git Tree Digest: {receipt['verified_tree_digest'][:16]}...")
        print(f"   Receipt Signature: {receipt['receipt_signature'][:16]}...")
        return 0
    except Exception as exc:
        print(f"❌ Failed to generate UAT receipt: {exc}")
        return 1


def dispatch_uat_command(
    args: argparse.Namespace,
    config: SpecOpsConfig,
    parser: argparse.ArgumentParser,
) -> int:
    """Dispatches 'spec-ops prd uat' subcommands."""
    action = getattr(args, "uat_action", None)
    if action == "status":
        return handle_uat_status(config, json_output=getattr(args, "json", False))
    if action == "sign":
        return handle_uat_sign(
            config,
            prd=args.prd,
            outcome=args.outcome,
            reviewer=args.reviewer,
            status=getattr(args, "status", "Approved"),
            notes=getattr(args, "notes", ""),
        )
    if action == "receipt":
        return handle_uat_receipt(
            config,
            prd=getattr(args, "prd", None),
            out=getattr(args, "out", None),
            verify=getattr(args, "verify", False),
        )

    parser.parse_args(["prd", "uat", "--help"])
    return 0
