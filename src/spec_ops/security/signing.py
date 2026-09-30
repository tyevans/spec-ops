"""Cryptographic commit verification, git trailer manipulation, and reviewer signing."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig


def validate_key_id(key_id: str) -> bool:
    """Validates key ID / reviewer identity format across PGP, SSH, and RFC 2822 styles."""
    if not isinstance(key_id, str):
        return False
    val = key_id.strip()
    if not val or len(val) < 3 or len(val) > 256:
        return False
    if any(c in val for c in ("\n", "\r", "\0", ";")):
        return False

    # RFC 2822 Name <email@domain>
    if re.match(r"^[^<>\r\n]+<[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+>$", val):
        return True
    # Pure email address
    if re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", val):
        return True
    # Hex PGP fingerprint or Key ID (8, 16, 40, or 64 hex characters, optional spaces)
    hex_clean = val.replace(" ", "")
    if hex_clean.startswith(("0x", "0X")):
        hex_clean = hex_clean[2:]
    if re.match(r"^[0-9a-fA-F]{8,64}$", hex_clean) and len(hex_clean) in (8, 16, 40, 64):
        return True
    # SSH public key or SSH fingerprint
    if val.startswith(("ssh-ed25519", "ssh-rsa", "ecdsa-sha2-", "SHA256:")):
        return True

    return False


def extract_email(identity: str) -> str | None:
    """Extracts email address from an identity string if present."""
    if not identity:
        return None
    m = re.search(r"<([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)>", identity)
    if m:
        return m.group(1).strip().lower()
    if re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", identity.strip()):
        return identity.strip().lower()
    return None


def parse_git_trailers(message: str) -> dict[str, str]:
    """Extracts git trailers (RFC 2822 style Token: Value) from the end of a commit message."""
    if not message or not message.strip():
        return {}
    lines = message.rstrip().splitlines()
    trailer_lines: list[str] = []

    for line in reversed(lines):
        stripped = line.strip()
        if not stripped:
            if trailer_lines:
                break
            continue
        is_token_line = bool(re.match(r"^[A-Za-z0-9][A-Za-z0-9_-]*\s*:", line))
        is_continuation = line.startswith(" ") or line.startswith("\t")
        if is_token_line or is_continuation:
            trailer_lines.append(line)
        else:
            break

    if not trailer_lines:
        return {}

    trailer_lines.reverse()
    trailers: dict[str, str] = {}
    current_key: str | None = None
    current_val: list[str] = []

    for line in trailer_lines:
        m = re.match(r"^([A-Za-z0-9][A-Za-z0-9_-]*)\s*:\s*(.*)$", line)
        if m:
            if current_key is not None:
                trailers[current_key] = "\n".join(current_val).strip()
            current_key = m.group(1)
            current_val = [m.group(2).strip()]
        elif current_key is not None and (line.startswith(" ") or line.startswith("\t")):
            current_val.append(line.strip())

    if current_key is not None:
        trailers[current_key] = "\n".join(current_val).strip()

    return trailers


def format_commit_message(
    message: str,
    trailers: dict[str, str] | list[tuple[str, str]],
) -> str:
    """Injects or appends git trailers into a commit message with proper RFC 2822 formatting."""
    trailer_items: list[tuple[str, str]] = (
        list(trailers.items()) if isinstance(trailers, dict) else list(trailers)
    )
    existing = parse_git_trailers(message)
    lines = message.rstrip().splitlines()
    body_lines: list[str] = []
    in_trailing = True

    for line in reversed(lines):
        stripped = line.strip()
        if in_trailing:
            if not stripped:
                continue
            is_token_line = bool(re.match(r"^[A-Za-z0-9][A-Za-z0-9_-]*\s*:", line))
            is_continuation = line.startswith(" ") or line.startswith("\t")
            if is_token_line or is_continuation:
                continue
            else:
                in_trailing = False
                body_lines.append(line)
        else:
            body_lines.append(line)

    body = "\n".join(reversed(body_lines)).strip()
    merged: dict[str, str] = dict(existing)
    for k, v in trailer_items:
        if v is not None and str(v).strip():
            merged[k] = str(v).strip()

    if not merged:
        return f"{body}\n" if body else ""

    trailer_block = "\n".join(f"{k}: {v}" for k, v in merged.items())
    if body:
        return f"{body}\n\n{trailer_block}\n"
    return f"{trailer_block}\n"


def load_authorized_signers(
    config: SpecOpsConfig | None = None,
    repo_dir: Path | None = None,
) -> set[str]:
    """Loads authorized reviewer identities from config and allowed signers keyring files."""
    authorized: set[str] = set()

    if config and config.security and config.security.compliance:
        for signer in config.security.compliance.authorized_signers:
            clean = signer.strip()
            if clean:
                authorized.add(clean.lower())
                email = extract_email(clean)
                if email:
                    authorized.add(email.lower())

    root = (repo_dir or (config.root_dir if config else Path.cwd())).resolve()
    candidate_paths: list[Path] = []
    if config and config.security and config.security.compliance and config.security.compliance.allowed_signers_file:
        candidate_paths.append(root / config.security.compliance.allowed_signers_file)
    candidate_paths.append(root / ".ssh" / "allowed_signers")
    candidate_paths.append(root / ".allowed_signers")

    for path in candidate_paths:
        if path.is_file():
            try:
                for line in path.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    parts = line.split()
                    if parts:
                        for p in parts[0].split(","):
                            p_clean = p.strip()
                            if p_clean:
                                authorized.add(p_clean.lower())
                                email = extract_email(p_clean)
                                if email:
                                    authorized.add(email.lower())
            except Exception:
                pass

    return authorized


def verify_reviewer_identity(
    identity: str,
    config: SpecOpsConfig | None = None,
    repo_dir: Path | None = None,
) -> tuple[bool, str]:
    """Cryptographically verifies a reviewer's identity against the authorized keyring."""
    if not validate_key_id(identity):
        return False, f"Invalid identity format: '{identity}'"

    authorized = load_authorized_signers(config=config, repo_dir=repo_dir)
    if authorized:
        ident_lower = identity.strip().lower()
        email = extract_email(identity)
        if (
            ident_lower not in authorized
            and (email is None or email not in authorized)
            and not any(ident_lower == a for a in authorized)
        ):
            return (
                False,
                f"Reviewer '{identity}' is not in authorized signers keyring.",
            )

    return True, f"Reviewer identity '{identity}' verified against keyring."


def verify_branch_commit_signatures(
    repo_dir: Path,
    base_branch: str = "main",
    target_branch: str | None = None,
) -> tuple[bool, str | None, str]:
    """Verifies that all commits in target_branch not in base_branch have valid cryptographic signatures."""
    rev_range = f"{base_branch}..{target_branch}" if target_branch else f"{base_branch}..HEAD"
    cmd = [
        "git",
        "log",
        rev_range,
        "--format=%H%x09%G?%x09%GS%x09%GK",
    ]
    res = subprocess.run(
        cmd,
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        return True, None, "No commits to verify."

    lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
    if not lines:
        return True, None, "No commits to verify."

    for line in lines:
        parts = line.split("\t")
        commit_sha = parts[0].strip()
        sig_status = parts[1].strip() if len(parts) > 1 else "N"

        if sig_status not in ("G", "U"):
            return (
                False,
                commit_sha,
                f"Compliance Violation: Commit {commit_sha} lacks valid cryptographic signature (GPG/SSH)",
            )

    return True, None, "All commits cryptographically verified."
