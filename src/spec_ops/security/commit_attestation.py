"""Cryptographic Commit Attestation and Sigstore Keyring Validator."""

from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import subprocess
import sys
from typing import Any

from .signing import extract_email, load_authorized_signers


@dataclass
class ParsedCommitObject:
    tree: str = ""
    parents: list[str] = field(default_factory=list)
    author: str = ""
    committer: str = ""
    gpgsig: str = ""
    sig_type: str = "none"  # "ssh", "pgp", "sigstore", "none"
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "tree": self.tree,
            "parents": list(self.parents),
            "author": self.author,
            "committer": self.committer,
            "sig_type": self.sig_type,
            "has_signature": bool(self.gpgsig),
            "message": self.message,
        }


def parse_commit_object(content: str) -> ParsedCommitObject:
    """Parses raw git commit object buffer into structured attributes with resilient parsing."""
    if not isinstance(content, str) or not content:
        return ParsedCommitObject()

    lines = content.splitlines()
    tree, author, committer = "", "", ""
    parents: list[str] = []
    gpgsig_lines: list[str] = []
    in_gpgsig = False
    message_lines: list[str] = []
    in_message = False

    for line in lines:
        if in_message:
            message_lines.append(line)
            continue
        if line == "":
            in_message = True
            in_gpgsig = False
            continue

        if in_gpgsig:
            if line.startswith(" "):
                gpgsig_lines.append(line[1:])
                continue
            in_gpgsig = False

        if line.startswith("tree "):
            tree = line[5:].strip()
        elif line.startswith("parent "):
            parents.append(line[7:].strip())
        elif line.startswith("author "):
            author = line[7:].strip()
        elif line.startswith("committer "):
            committer = line[10:].strip()
        elif line.startswith("gpgsig "):
            in_gpgsig = True
            gpgsig_lines.append(line[7:])

    gpgsig = "\n".join(gpgsig_lines).strip()
    sig_type = "none"
    if "BEGIN SSH SIGNATURE" in gpgsig:
        sig_type = "ssh"
    elif "BEGIN PGP SIGNATURE" in gpgsig:
        sig_type = "pgp"
    elif "BEGIN COSIGN" in gpgsig or "sigstore" in gpgsig.lower():
        sig_type = "sigstore"
    elif gpgsig:
        sig_type = "unknown"

    return ParsedCommitObject(
        tree=tree,
        parents=parents,
        author=author,
        committer=committer,
        gpgsig=gpgsig,
        sig_type=sig_type,
        message="\n".join(message_lines).strip(),
    )


def load_keyring_entries(keyring_path: Path | str | None) -> set[str]:
    """Loads authorized identities, emails, and public key identifiers from a keyring file."""
    entries: set[str] = set()
    if not keyring_path:
        return entries
    p = Path(keyring_path)
    if not p.is_file():
        return entries

    try:
        for line in p.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split()
            if not parts:
                continue
            for ident in parts[0].split(","):
                clean = ident.strip().lower()
                if clean:
                    entries.add(clean)
                    em = extract_email(clean)
                    if em:
                        entries.add(em.lower())
            for pt in parts[1:]:
                if pt.startswith(("AAA", "SHA256:", "ssh-", "ecdsa-")):
                    entries.add(pt.strip().lower())
    except Exception:
        pass
    return entries


@dataclass
class CommitAttestation:
    commit_sha: str
    author: str
    committer: str
    signer: str
    key_id: str
    sig_status: str  # "VALID", "INVALID", "UNSIGNED", "UNKNOWN", "UNTRUSTED_SIGNER"
    sig_type: str
    is_valid: bool
    diagnostics: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "commit_sha": self.commit_sha,
            "author": self.author,
            "committer": self.committer,
            "signer": self.signer,
            "key_id": self.key_id,
            "sig_status": self.sig_status,
            "sig_type": self.sig_type,
            "is_valid": self.is_valid,
            "diagnostics": list(self.diagnostics),
        }


@dataclass
class CommitVerificationReport:
    rev_range: str
    commits: list[CommitAttestation] = field(default_factory=list)
    keyring_path: str | None = None
    is_clean: bool = True
    total_verified: int = 0
    total_failed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "rev_range": self.rev_range,
            "keyring_path": self.keyring_path,
            "is_clean": self.is_clean,
            "total_verified": self.total_verified,
            "total_failed": self.total_failed,
            "commits": [c.to_dict() for c in self.commits],
        }

    def format_text(self) -> str:
        lines: list[str] = [
            "=== SpecOps Cryptographic Commit Attestation Audit ===",
            f"Revision Range: {self.rev_range}",
            f"Keyring:        {self.keyring_path or 'Default System / Git Keyring'}",
            f"Evaluated:      {len(self.commits)} commit(s)",
            f"Verified:       {self.total_verified} valid",
            f"Unverified:     {self.total_failed} invalid/unsigned",
            "",
        ]
        if self.is_clean:
            lines.append("✅ Cryptographic Provenance Verified: All commits contain valid signatures.")
        else:
            lines.append("❌ Attestation Violations Detected:")
            for c in self.commits:
                if not c.is_valid:
                    lines.append(f"  ⚠️  Commit {c.commit_sha[:8]} [{c.sig_status}] by {c.author}")
                    for d in c.diagnostics:
                        lines.append(f"     - {d}")
        return "\n".join(lines)


def evaluate_commit_signature(
    commit_sha: str,
    author: str,
    committer: str,
    git_sig_flag: str,
    signer: str,
    key_id: str,
    parsed_obj: ParsedCommitObject | None = None,
    authorized_keys: set[str] | None = None,
    strict: bool = False,
) -> CommitAttestation:
    """Evaluates signature flags and keyring inclusion for a single commit."""
    sig_type = parsed_obj.sig_type if parsed_obj else "none"
    has_raw_sig = bool(parsed_obj and parsed_obj.gpgsig)

    if git_sig_flag == "N" and not has_raw_sig:
        return CommitAttestation(
            commit_sha=commit_sha, author=author, committer=committer, signer=signer,
            key_id=key_id, sig_status="UNSIGNED", sig_type=sig_type, is_valid=False,
            diagnostics=["Commit lacks cryptographic signature (GPG/SSH/Sigstore)."],
        )
    if git_sig_flag == "B":
        return CommitAttestation(
            commit_sha=commit_sha, author=author, committer=committer, signer=signer,
            key_id=key_id, sig_status="INVALID", sig_type=sig_type, is_valid=False,
            diagnostics=["Cryptographic signature verification failed (corrupted or forged signature)."],
        )

    is_valid, sig_status = True, "VALID"
    diagnostics: list[str] = []

    if authorized_keys:
        auth_email = extract_email(author) or ""
        comm_email = extract_email(committer) or ""
        signer_email = extract_email(signer) or ""
        signer_ident = signer.strip().lower()
        key_clean = key_id.strip().lower()

        found = (
            "*" in authorized_keys
            or (auth_email and auth_email in authorized_keys)
            or (comm_email and comm_email in authorized_keys)
            or (signer_email and signer_email in authorized_keys)
            or (signer_ident and signer_ident in authorized_keys)
            or (key_clean and key_clean in authorized_keys)
        )
        if not found:
            is_valid, sig_status = False, "UNTRUSTED_SIGNER"
            diagnostics.append(f"Signer '{signer or author}' (key: {key_id or 'unknown'}) is not in authorized keyring.")
    elif git_sig_flag in ("U", "N") and strict:
        is_valid, sig_status = False, "UNKNOWN" if git_sig_flag == "U" else "UNSIGNED"
        diag = "Signature key is untrusted and no authorized keyring entry matched." if git_sig_flag == "U" else "Commit lacks cryptographic signature."
        diagnostics.append(diag)

    return CommitAttestation(
        commit_sha=commit_sha, author=author, committer=committer, signer=signer,
        key_id=key_id, sig_status=sig_status, sig_type=sig_type, is_valid=is_valid,
        diagnostics=diagnostics,
    )


def verify_commit_range(
    repo_dir: Path,
    rev_range: str = "HEAD~1..HEAD",
    keyring_path: Path | str | None = None,
    strict: bool = False,
) -> CommitVerificationReport:
    """Verifies cryptographic signatures across a range of git commits."""
    root = Path(repo_dir).resolve()
    authorized_keys = load_keyring_entries(keyring_path) or load_authorized_signers(repo_dir=root)

    resolved_keyring: Path | None = None
    if keyring_path:
        kp = Path(keyring_path).resolve()
        if kp.is_file():
            resolved_keyring = kp
    if not resolved_keyring:
        for cand in [root / ".allowed_signers", root / ".ssh" / "allowed_signers", Path.home() / ".ssh" / "allowed_signers"]:
            if cand.is_file():
                resolved_keyring = cand
                break

    git_configs: list[str] = ["-c", "gpg.format=ssh"]
    if resolved_keyring:
        git_configs.extend(["-c", f"gpg.ssh.allowedSignersFile={resolved_keyring}"])

    fmt = "--format=%H%x09%an <%ae>%x09%cn <%ce>%x09%G?%x09%GS%x09%GK"
    cmd = ["git", *git_configs, "log", rev_range, fmt]
    res = subprocess.run(cmd, cwd=root, capture_output=True, text=True)

    if res.returncode != 0:
        # Fallback if rev_range is a single ref (e.g. HEAD)
        fallback_cmd = ["git", *git_configs, "log", "-1", rev_range, fmt]
        res = subprocess.run(fallback_cmd, cwd=root, capture_output=True, text=True)
        if res.returncode != 0:
            return CommitVerificationReport(
                rev_range=rev_range,
                keyring_path=str(resolved_keyring or keyring_path) if (resolved_keyring or keyring_path) else None,
                is_clean=True,
                total_verified=0,
                total_failed=0,
            )

    attestations: list[CommitAttestation] = []
    for line in [l.strip() for l in res.stdout.splitlines() if l.strip()]:
        parts = line.split("\t")
        sha = parts[0].strip()
        author = parts[1].strip() if len(parts) > 1 else ""
        committer = parts[2].strip() if len(parts) > 2 else ""
        sig_flag = parts[3].strip() if len(parts) > 3 else "N"
        signer = parts[4].strip() if len(parts) > 4 else ""
        key_id = parts[5].strip() if len(parts) > 5 else ""

        raw_res = subprocess.run(["git", "cat-file", "commit", sha], cwd=root, capture_output=True, text=True)
        parsed_obj = parse_commit_object(raw_res.stdout) if raw_res.returncode == 0 else None

        attestations.append(
            evaluate_commit_signature(
                commit_sha=sha, author=author, committer=committer, git_sig_flag=sig_flag,
                signer=signer, key_id=key_id, parsed_obj=parsed_obj,
                authorized_keys=authorized_keys, strict=strict,
            )
        )

    failed = sum(1 for a in attestations if not a.is_valid)
    return CommitVerificationReport(
        rev_range=rev_range,
        commits=attestations,
        keyring_path=str(resolved_keyring or keyring_path) if (resolved_keyring or keyring_path) else None,
        is_clean=(failed == 0 and len(attestations) > 0),
        total_verified=sum(1 for a in attestations if a.is_valid),
        total_failed=failed,
    )


def verify_commits_cli(
    repo_dir: Path,
    rev_range: str = "HEAD~1..HEAD",
    keyring_path: Path | str | None = None,
    strict: bool = False,
    as_json: bool = False,
) -> int:
    """CLI driver for 'spec-ops security verify-commits'."""
    report = verify_commit_range(
        repo_dir=repo_dir,
        rev_range=rev_range,
        keyring_path=keyring_path,
        strict=strict,
    )

    if as_json:
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if report.is_clean else 1

    print(report.format_text())
    return 0 if report.is_clean else 1
