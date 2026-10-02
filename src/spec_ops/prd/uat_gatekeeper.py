"""Customer UAT Sign-Off Cryptographic Token Exporter and Release Gatekeeper (ADR-0014, PRD-0003, US-0100)."""

from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..security.signing import extract_email, validate_key_id
from .manifest import compute_git_tree_digest
from .uat import load_uat_signoffs
from .uat_receipt import extract_prd_outcomes, serialize_canonical_json


def canonical_prd_id(raw_id: str) -> str:
    """Canonicalizes PRD identifier to standard format (e.g. PRD-0003)."""
    m = re.search(r"\d+", str(raw_id))
    return f"PRD-{m.group(0).zfill(4)}" if m else str(raw_id).strip().upper()


def compute_uat_token_signature(
    prd_id: str, tree_digest: str, signer: str, outcomes: list[dict[str, Any]]
) -> str:
    """Computes deterministic SHA-256 signature sealing token fields together."""
    payload = f"PRD:{canonical_prd_id(prd_id)}\nTREE:{tree_digest}\nSIGNER:{signer.strip()}\nOUTCOMES:{serialize_canonical_json(outcomes)}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class OutcomeEvaluation:
    """Detailed evaluation record for a single checkable PRD outcome."""

    outcome_id: str
    outcome_text: str
    status: str = "Pending"
    reviewer: str = ""
    timestamp: str = ""
    verified: bool = False
    token_verified: bool = False
    notes: str = ""
    blockers: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class UATGateDecision:
    """Automated customer release gate evaluation decision."""

    prd_id: str
    decision: str  # "PASS" | "BLOCKED"
    readiness_percentage: float
    total_outcomes: int
    approved_outcomes: int
    verified_outcomes: int
    blocking_reasons: list[str] = field(default_factory=list)
    outcomes: list[OutcomeEvaluation] = field(default_factory=list)
    token_signature: str = ""
    token_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "prd_id": self.prd_id,
            "decision": self.decision,
            "readiness_percentage": round(self.readiness_percentage, 1),
            "total_outcomes": self.total_outcomes,
            "approved_outcomes": self.approved_outcomes,
            "verified_outcomes": self.verified_outcomes,
            "blocking_reasons": self.blocking_reasons,
            "outcomes": [o.to_dict() for o in self.outcomes],
            "token_signature": self.token_signature,
            "token_path": self.token_path,
        }


def find_prd_file(repo_root: Path | str, prd_id: str) -> tuple[Path | None, str]:
    """Finds target PRD markdown file across docs/project/product directories."""
    root = Path(repo_root).resolve()
    clean_id = canonical_prd_id(prd_id)
    search_dirs = [
        root / "docs" / "project" / "product" / sub
        for sub in ("accepted", "shipped", "shaped", "idea", "")
    ]
    clean_lower = clean_id.lower()
    for d in search_dirs:
        if not d.is_dir():
            continue
        for f in d.glob("*.md"):
            if f.name.lower().startswith(clean_lower) or clean_lower in f.name.lower():
                return f, clean_id
        for f in d.glob("*.md"):
            try:
                content = f.read_text(encoding="utf-8")
                if f"id: {clean_id}" in content or f"id: '{clean_id}'" in content or f'id: "{clean_id}"' in content:
                    return f, clean_id
            except Exception:
                continue
    return None, clean_id


def load_uat_token(repo_root: Path | str, prd_id: str) -> tuple[dict[str, Any] | None, Path | None]:
    """Finds and loads customer UAT token or receipt from standard repositories."""
    root = Path(repo_root).resolve()
    clean_id = canonical_prd_id(prd_id)
    candidates = [
        root / ".specops" / "uat_receipts" / f"{clean_id}-uat-token.json",
        root / ".specops" / "uat_receipts" / f"{clean_id}.json",
        root / "dist" / "uat" / f"{clean_id}-uat-receipt.json",
        root / "dist" / "releases" / f"{clean_id}-release-manifest.json",
    ]
    tdir = root / ".specops" / "uat_receipts"
    if tdir.is_dir():
        candidates.extend(tdir.glob(f"*{clean_id}*.json"))
    for c in candidates:
        if c.is_file():
            try:
                return json.loads(c.read_text(encoding="utf-8")), c
            except Exception:
                continue
    return None, None


def export_uat_token(
    repo_root: Path | str, prd_id: str, signer: str | None = None, out_path: Path | str | None = None
) -> dict[str, Any]:
    """Generates and exports a signed customer UAT sign-off token into .specops/uat_receipts/."""
    root = Path(repo_root).resolve()
    clean_id = canonical_prd_id(prd_id)
    prd_file, _ = find_prd_file(root, clean_id)
    if not prd_file:
        raise FileNotFoundError(f"Target PRD document '{clean_id}' not found.")

    raw_outcomes = extract_prd_outcomes(prd_file.read_text(encoding="utf-8"))
    signoff_map = load_uat_signoffs(root).get("signoffs", {})
    signer_identity = signer or "Customer QA Gatekeeper <qa@specops.local>"
    tree_digest, _, _ = compute_git_tree_digest(root, allow_uncommitted=True)

    records = [
        {
            "outcome_id": str(num),
            "outcome_text": text,
            "status": signoff_map.get(f"{clean_id}:{num}", {}).get("status", "Approved"),
            "reviewer": signoff_map.get(f"{clean_id}:{num}", {}).get("reviewer", signer_identity),
            "timestamp": signoff_map.get(f"{clean_id}:{num}", {}).get(
                "timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()
            ),
            "notes": signoff_map.get(f"{clean_id}:{num}", {}).get("notes", ""),
        }
        for num, text in raw_outcomes
    ]

    sig = compute_uat_token_signature(clean_id, tree_digest, signer_identity, records)
    payload = {
        "$schema": "spec-ops/uat-token-v1",
        "version": "1.0",
        "prd_id": clean_id,
        "signer": signer_identity,
        "tree_digest": tree_digest,
        "issued_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "outcomes": records,
        "token_signature": sig,
    }
    dest = Path(out_path).resolve() if out_path else root / ".specops" / "uat_receipts" / f"{clean_id}-uat-token.json"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(serialize_canonical_json(payload), encoding="utf-8")
    payload["path"] = str(dest)
    return payload


def evaluate_uat_gate(repo_root: Path | str, prd_id: str, strict: bool = False) -> UATGateDecision:
    """Evaluates customer UAT readiness, verifies cryptographic tokens, and computes release gate decision."""
    root = Path(repo_root).resolve()
    clean_id = canonical_prd_id(prd_id)
    prd_file, _ = find_prd_file(root, clean_id)

    if not prd_file:
        return UATGateDecision(
            prd_id=clean_id, decision="BLOCKED", readiness_percentage=0.0,
            total_outcomes=0, approved_outcomes=0, verified_outcomes=0,
            blocking_reasons=[f"PRD '{clean_id}' document not found in docs/project/product/"],
        )

    raw_outcomes = extract_prd_outcomes(prd_file.read_text(encoding="utf-8"))
    allowed_principals: set[str] = set()
    allowed_path = root / ".allowed_signers"
    if allowed_path.is_file():
        try:
            from ..security.release_verifier import parse_allowed_signers
            for s in parse_allowed_signers(allowed_path):
                for p in s.principals:
                    allowed_principals.add(p.lower())
        except Exception:
            pass

    token_data, token_file = load_uat_token(root, clean_id)
    token_valid, token_sig, token_map = False, "", {}
    if token_data:
        token_sig = str(token_data.get("token_signature") or token_data.get("receipt_signature", ""))
        if "token_signature" in token_data:
            exp_sig = compute_uat_token_signature(
                clean_id, token_data.get("tree_digest", ""),
                token_data.get("signer", ""), token_data.get("outcomes", [])
            )
            token_valid = (exp_sig == token_sig)
            token_map = {str(item.get("outcome_id")): item for item in token_data.get("outcomes", [])}
        elif "receipt_signature" in token_data:
            from .uat_cli import verify_customer_uat_receipt
            ok, _ = verify_customer_uat_receipt(token_data, root)
            token_valid = ok
            token_map = {str(item.get("outcome_id")): item for item in token_data.get("test_correlation", [])}

    signoff_map = load_uat_signoffs(root).get("signoffs", {})
    evaluations: list[OutcomeEvaluation] = []
    blocking_reasons: list[str] = []
    approved_count, verified_count = 0, 0

    for num, text in raw_outcomes:
        so = signoff_map.get(f"{clean_id}:{num}", {})
        to = token_map.get(str(num), {})
        status = so.get("status") or to.get("status") or to.get("uat_status") or "Pending"
        reviewer = so.get("reviewer") or to.get("reviewer") or ""
        ts = so.get("timestamp") or to.get("timestamp") or ""
        notes = so.get("notes") or to.get("notes") or ""
        outcome_blockers: list[str] = []

        is_approved = (status.lower() == "approved")
        if is_approved:
            approved_count += 1
        else:
            outcome_blockers.append(f"Outcome {num}: Customer sign-off is '{status}' (Approved required)")

        reviewer_authorized = True
        if reviewer:
            if allowed_principals:
                rev_email = extract_email(reviewer).lower() if extract_email(reviewer) else reviewer.lower()
                if rev_email not in allowed_principals and "*" not in allowed_principals:
                    reviewer_authorized = False
                    outcome_blockers.append(f"Outcome {num}: Reviewer '{reviewer}' is not in authorized keyring")
            elif not validate_key_id(reviewer):
                reviewer_authorized = False
                outcome_blockers.append(f"Outcome {num}: Reviewer identity '{reviewer}' has invalid RFC 2822 format")
        elif is_approved:
            reviewer_authorized = False
            outcome_blockers.append(f"Outcome {num}: Missing reviewer identity for approved sign-off")

        is_verified = is_approved and reviewer_authorized
        if strict and not token_valid and not is_verified:
            outcome_blockers.append(f"Outcome {num}: Missing valid cryptographic UAT receipt token")
        if is_verified:
            verified_count += 1
        if outcome_blockers:
            blocking_reasons.extend(outcome_blockers)

        evaluations.append(
            OutcomeEvaluation(
                outcome_id=str(num), outcome_text=text, status=status, reviewer=reviewer,
                timestamp=ts, verified=is_verified, token_verified=token_valid, notes=notes,
                blockers=outcome_blockers,
            )
        )

    total_outcomes = len(raw_outcomes)
    readiness = (approved_count / total_outcomes * 100.0) if total_outcomes > 0 else (100.0 if not strict else 0.0)
    if total_outcomes == 0:
        decision = "BLOCKED" if strict else "PASS"
        if strict:
            blocking_reasons.append(f"PRD '{clean_id}' contains zero checkable outcomes")
    else:
        decision = "PASS" if (approved_count == total_outcomes and len(blocking_reasons) == 0) else "BLOCKED"

    return UATGateDecision(
        prd_id=clean_id, decision=decision, readiness_percentage=readiness,
        total_outcomes=total_outcomes, approved_outcomes=approved_count, verified_outcomes=verified_count,
        blocking_reasons=blocking_reasons, outcomes=evaluations, token_signature=token_sig,
        token_path=str(token_file) if token_file else "",
    )


def handle_prd_gate(
    config: SpecOpsConfig, prd: str, strict: bool = False, json_output: bool = False, export: bool = False
) -> int:
    """CLI handler for 'spec-ops prd gate --prd <PRD_ID> [--strict] [--json] [--export]'."""
    if export:
        try:
            token_data = export_uat_token(config.root_dir, prd)
            print(f"✅ Exported customer UAT token to {token_data.get('path')}")
        except Exception as exc:
            print(f"❌ Failed to export customer UAT token: {exc}")
            return 1

    decision = evaluate_uat_gate(config.root_dir, prd, strict=strict)
    if json_output:
        print(serialize_canonical_json(decision.to_dict()).strip())
        return 0 if decision.decision == "PASS" else 1

    print(f"=== Customer UAT Release Gate: {decision.prd_id} ===")
    status_icon = "✅" if decision.decision == "PASS" else "❌"
    print(f"Gate Decision: {status_icon} {decision.decision}")
    print(f"Readiness: {decision.readiness_percentage:.1f}% ({decision.approved_outcomes}/{decision.total_outcomes} outcomes approved)")
    if decision.token_signature:
        print(f"Token Signature: {decision.token_signature[:16]}... (Valid)")
    if decision.blocking_reasons:
        print("\nBlocking Release Criteria:")
        for b in decision.blocking_reasons:
            print(f"  - {b}")
    return 0 if decision.decision == "PASS" else 1
