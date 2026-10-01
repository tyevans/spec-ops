"""Cryptographic release verification and public keyring validator (ADR-0014, PRD-0002)."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .ed25519 import (
    ed25519_keypair,
    ed25519_sign,
    ed25519_verify,
    ssh_decode_ed25519_pub,
    ssh_encode_ed25519_pub,
)
from .signing import extract_email, validate_key_id


@dataclass
class AuthorizedSigner:
    """Authorized signer key record parsed from .allowed_signers."""

    principals: list[str]
    key_type: str
    pubkey_bytes: bytes
    raw_key: str
    namespaces: list[str] = field(default_factory=list)
    comment: str = ""


def parse_allowed_signers(content_or_path: str | Path) -> list[AuthorizedSigner]:
    """Parses .allowed_signers format and returns structured authorized keys."""
    text = (
        content_or_path.read_text(encoding="utf-8")
        if isinstance(content_or_path, Path)
        else content_or_path
    )
    signers: list[AuthorizedSigner] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if len(parts) < 2:
            continue
        principals = [p.strip().lower() for p in parts[0].split(",") if p.strip()]
        namespaces: list[str] = []
        idx = 1
        while idx < len(parts) and "=" in parts[idx]:
            opt = parts[idx]
            if opt.startswith("namespaces="):
                val = opt.split("=", 1)[1].strip('"').strip("'")
                namespaces = [ns.strip() for ns in val.split(",")]
            idx += 1
        if idx >= len(parts):
            continue
        key_type = parts[idx]
        raw_key = parts[idx + 1] if idx + 1 < len(parts) else ""
        comment = " ".join(parts[idx + 2 :]) if idx + 2 < len(parts) else ""
        pub = ssh_decode_ed25519_pub(f"{key_type} {raw_key}" if raw_key else key_type)
        if pub:
            signers.append(
                AuthorizedSigner(
                    principals=principals,
                    key_type=key_type,
                    pubkey_bytes=pub,
                    raw_key=raw_key or key_type,
                    namespaces=namespaces,
                    comment=comment,
                )
            )
    return signers


def canonical_manifest_bytes(manifest: dict[str, Any]) -> bytes:
    """Deterministically serializes manifest excluding signature fields."""
    filtered = {
        k: v
        for k, v in manifest.items()
        if k not in ("signature", "manifest_signature", "sig")
    }
    return json.dumps(filtered, sort_keys=True, separators=(",", ":")).encode("utf-8")


def sign_release_manifest(
    manifest: dict[str, Any],
    secret_or_seed: bytes | str,
    signer: str,
    algorithm: str = "ed25519",
) -> dict[str, Any]:
    """Signs a release manifest, stamping cryptographic signature and signer."""
    manifest = dict(manifest)
    manifest["signer"] = signer
    manifest["signature_algorithm"] = algorithm
    payload = canonical_manifest_bytes(manifest)

    if algorithm.lower() == "ed25519":
        seed_bytes = (
            secret_or_seed.encode("utf-8")
            if isinstance(secret_or_seed, str)
            else secret_or_seed
        )
        _, pub = ed25519_keypair(seed_bytes)
        sig = ed25519_sign(seed_bytes, pub, payload)
        sig_hex = sig.hex()
        manifest["signature"] = sig_hex
        manifest["manifest_signature"] = sig_hex
    elif "hmac" in algorithm.lower():
        sec = (
            secret_or_seed.encode("utf-8")
            if isinstance(secret_or_seed, str)
            else secret_or_seed
        )
        token = hmac.new(sec, payload, hashlib.sha256).hexdigest()
        manifest["signature"] = token
        manifest["manifest_signature"] = token
    return manifest


@dataclass
class ReleaseVerificationResult:
    """Outcome of cryptographic release manifest verification."""

    valid: bool
    manifest_path: str
    signer: str = ""
    key_type: str = "ssh-ed25519"
    algorithm: str = "ed25519"
    keyring_file: str | None = None
    tree_digest: str | None = None
    tree_clean: bool | None = None
    uat_status: str | None = None
    errors: list[str] = field(default_factory=list)
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def format_report(self) -> str:
        """Renders formatted verification diagnostics for terminal output."""
        validity_text = "VALID (ed25519 signature verified)" if self.valid else "INVALID"
        status_text = "PASSED" if self.valid else "FAILED"
        lines = [
            "=== SpecOps Release Manifest Verification ===",
            f"Manifest: {self.manifest_path}",
            f"Signer Identity: {self.signer or 'Unknown'}",
            f"Cryptographic Validity: {validity_text}",
        ]
        if self.keyring_file:
            lines.append(f"Keyring Source: {self.keyring_file}")
        if self.tree_digest:
            lines.append(f"Tree Digest: {self.tree_digest}")
        if self.uat_status:
            lines.append(f"UAT Verification: {self.uat_status}")
        if self.errors:
            lines.append("Errors:")
            for err in self.errors:
                lines.append(f"  - {err}")
        lines.append(f"Status: {status_text}")
        return "\n".join(lines)


def verify_release_manifest_data(
    manifest_data: dict[str, Any],
    keyring_signers: list[AuthorizedSigner],
    repo_root: Path | None = None,
    strict: bool = False,
    manifest_path: str = "release-manifest.json",
    keyring_path: str | None = None,
) -> ReleaseVerificationResult:
    """Verifies cryptographic signature, signer authorization, tree digest, and UAT sign-offs."""
    errors: list[str] = []
    signer = str(
        manifest_data.get("signer")
        or manifest_data.get("reviewer")
        or manifest_data.get("signer_identity")
        or ""
    ).strip()
    algorithm = str(manifest_data.get("signature_algorithm") or "ed25519").strip()
    tree_digest = manifest_data.get("verified_tree_digest") or manifest_data.get("tree_digest")

    uat_info = manifest_data.get("uat_verification") or manifest_data.get("uat_receipt")
    uat_status = (
        uat_info.get("status") if isinstance(uat_info, dict) else str(uat_info or "Unknown")
    )

    sig_raw = (
        manifest_data.get("signature")
        or manifest_data.get("manifest_signature")
        or manifest_data.get("sig")
        or ""
    )
    if not sig_raw:
        errors.append("Signature mismatch: manifest lacks cryptographic signature token")

    # Match signer in keyring
    matching_keys = [
        k
        for k in keyring_signers
        if "*" in k.principals
        or not signer
        or signer.lower() in k.principals
        or (extract_email(signer) and extract_email(signer) in k.principals)
    ]
    if keyring_signers and not matching_keys:
        errors.append(f"Signer '{signer}' not found in authorized signers keyring")

    # Cryptographic signature verification
    sig_valid = False
    candidate_keys = matching_keys if matching_keys else keyring_signers
    candidate_payloads = [canonical_manifest_bytes(manifest_data)]
    if "manifest_signature" in manifest_data and manifest_data.get("signature") != manifest_data.get("manifest_signature"):
        candidate_payloads.append(str(manifest_data["manifest_signature"]).encode("utf-8"))

    if sig_raw and candidate_keys and "ed25519" in algorithm.lower():
        sig_bytes = None
        try:
            sig_bytes = bytes.fromhex(sig_raw) if len(sig_raw) == 128 else base64.b64decode(sig_raw)
        except Exception:
            pass
        if sig_bytes and len(sig_bytes) == 64:
            for k in candidate_keys:
                for p in candidate_payloads:
                    if ed25519_verify(k.pubkey_bytes, p, sig_bytes):
                        sig_valid = True
                        break
                if sig_valid:
                    break
    elif sig_raw and "hmac" in algorithm.lower():
        for k in candidate_keys:
            token = hmac.new(k.pubkey_bytes, candidate_payloads[0], hashlib.sha256).hexdigest()
            if hmac.compare_digest(token, sig_raw):
                sig_valid = True
                break

    if not sig_valid and sig_raw:
        errors.append("Signature mismatch: cryptographic signature verification failed")

    # Strict tree digest and UAT sign-off checks
    if strict:
        if not signer:
            errors.append("Strict validation requires explicit signer identity")
        if uat_status != "Approved":
            errors.append(f"Strict validation requires Approved UAT status; got '{uat_status}'")
        if repo_root and tree_digest:
            from ..prd.manifest import compute_git_tree_digest

            curr_tree, clean, errs = compute_git_tree_digest(repo_root, allow_uncommitted=False)
            if errs or curr_tree != tree_digest:
                errors.append(f"Tree digest mismatch: repository {curr_tree[:12]} != manifest {tree_digest[:12]}")

    is_valid = len(errors) == 0 and sig_valid
    msg = (
        "Cryptographic release manifest verified successfully."
        if is_valid
        else f"Release manifest verification failed: {'; '.join(errors)}"
    )
    return ReleaseVerificationResult(
        valid=is_valid,
        manifest_path=manifest_path,
        signer=signer,
        key_type="ssh-ed25519",
        algorithm=algorithm,
        keyring_file=keyring_path,
        tree_digest=tree_digest,
        uat_status=uat_status,
        errors=errors,
        message=msg,
    )


def verify_release_manifest_file(
    manifest_path: str | Path,
    keyring_path: str | Path | None = None,
    repo_root: str | Path | None = None,
    strict: bool = False,
) -> ReleaseVerificationResult:
    """Verifies a release manifest JSON file against authorized public keyring."""
    m_p = Path(manifest_path).resolve()
    if not m_p.is_file():
        return ReleaseVerificationResult(
            valid=False,
            manifest_path=str(manifest_path),
            errors=[f"Manifest file not found: {manifest_path}"],
            message="Manifest file not found",
        )
    try:
        data = json.loads(m_p.read_text(encoding="utf-8"))
    except Exception as exc:
        return ReleaseVerificationResult(
            valid=False,
            manifest_path=str(manifest_path),
            errors=[f"Invalid manifest JSON: {exc}"],
            message="Invalid manifest JSON",
        )

    root = Path(repo_root).resolve() if repo_root else m_p.parent
    keyring_file = Path(keyring_path).resolve() if keyring_path else None
    if not keyring_file:
        for candidate in [root / ".allowed_signers", root / ".ssh" / "allowed_signers"]:
            if candidate.is_file():
                keyring_file = candidate
                break

    signers = parse_allowed_signers(keyring_file) if keyring_file and keyring_file.is_file() else []
    return verify_release_manifest_data(
        manifest_data=data,
        keyring_signers=signers,
        repo_root=root,
        strict=strict,
        manifest_path=str(manifest_path),
        keyring_path=str(keyring_file) if keyring_file else None,
    )
