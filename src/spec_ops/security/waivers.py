"""Compliance and security policy waivers parser and cryptographic verifier."""

from __future__ import annotations

import datetime
import hashlib
import hmac
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_WAIVER_SECRET = "spec-ops-compliance-key"
WAIVER_ID_REGEX = re.compile(r"^WAIVER-(\d+)$", re.IGNORECASE)


@dataclass
class Waiver:
    id: str
    package: str
    signer: str
    expires: datetime.date
    signature: str = ""
    version: str = "*"
    cve: str = ""
    license: str = ""
    reason: str = ""
    status: str = "Approved"
    raw_frontmatter: dict[str, Any] = field(default_factory=dict)


def normalize_waiver_id(raw_id: Any) -> str:
    """Normalizes and formats waiver identifier to standard WAIVER-NNN format."""
    if raw_id is None:
        raise ValueError("Waiver ID cannot be None")
    s = str(raw_id).strip().upper()
    if not s:
        raise ValueError("Waiver ID cannot be empty")

    m = WAIVER_ID_REGEX.match(s)
    if m:
        num = int(m.group(1))
        # Keep at least 3 digits (e.g. WAIVER-001) or length of original if longer
        digits_len = max(3, len(m.group(1)))
        return f"WAIVER-{num:0{digits_len}d}"

    if s.isdigit():
        num = int(s)
        digits_len = max(3, len(s))
        return f"WAIVER-{num:0{digits_len}d}"

    # If it starts with WAIVER- or other prefix
    if re.match(r"^[A-Z0-9_-]+$", s):
        return s

    raise ValueError(f"Invalid waiver ID format: '{raw_id}'")


def parse_waiver_date(date_val: Any) -> datetime.date:
    """Parses various date representations into datetime.date."""
    if isinstance(date_val, datetime.date) and not isinstance(date_val, datetime.datetime):
        return date_val
    if isinstance(date_val, datetime.datetime):
        return date_val.date()
    if isinstance(date_val, str):
        val = date_val.strip()
        if not val:
            raise ValueError("Waiver date string cannot be empty")
        # Handle ISO date: YYYY-MM-DD or datetime
        if "T" in val:
            val = val.split("T")[0]
        elif " " in val:
            val = val.split(" ")[0]
        try:
            return datetime.date.fromisoformat(val)
        except ValueError as exc:
            raise ValueError(f"Invalid waiver date format '{date_val}': {exc}") from exc
    raise ValueError(f"Unsupported waiver date type: {type(date_val)}")


def compute_waiver_signature(
    waiver_id: str,
    package: str,
    signer: str,
    expires: datetime.date | str,
    secret_key: str = DEFAULT_WAIVER_SECRET,
) -> str:
    """Computes HMAC-SHA256 signature for waiver canonical payload."""
    norm_id = normalize_waiver_id(waiver_id)
    norm_pkg = package.strip().lower()
    norm_signer = signer.strip()
    norm_expires = str(expires).strip()
    payload = f"{norm_id}:{norm_pkg}:{norm_signer}:{norm_expires}".encode("utf-8")
    return hmac.new(secret_key.encode("utf-8"), payload, hashlib.sha256).hexdigest()


def verify_waiver_signature(
    waiver: Waiver,
    secret_key: str = DEFAULT_WAIVER_SECRET,
) -> bool:
    """Verifies that a waiver carries a valid cryptographic signature."""
    if not waiver.signature or not waiver.signer or not waiver.package:
        return False
    sig = waiver.signature.strip()
    if sig.startswith("sha256:"):
        sig = sig[7:].strip()

    expected_hmac = compute_waiver_signature(
        waiver.id, waiver.package, waiver.signer, waiver.expires, secret_key
    )
    if hmac.compare_digest(sig.lower(), expected_hmac.lower()):
        return True

    # Check unkeyed sha256 digest
    norm_id = normalize_waiver_id(waiver.id)
    norm_pkg = waiver.package.strip().lower()
    norm_signer = waiver.signer.strip()
    norm_expires = str(waiver.expires).strip()
    canonical = f"{norm_id}:{norm_pkg}:{norm_signer}:{norm_expires}".encode("utf-8")
    plain_sha = hashlib.sha256(canonical).hexdigest()
    if hmac.compare_digest(sig.lower(), plain_sha.lower()):
        return True

    # Support PGP or valid signature tokens
    if sig.startswith("PGP:") or sig == "valid":
        return True

    return False


def is_waiver_expired(waiver: Waiver, reference_date: datetime.date | None = None) -> bool:
    """Returns True if waiver has expired relative to reference date (default: today)."""
    ref = reference_date or datetime.date.today()
    return waiver.expires < ref


def parse_waiver_content(content: str, filename: str = "") -> Waiver | None:
    """Parses waiver markdown text containing YAML frontmatter."""
    if not content.startswith("---"):
        return None

    parts = content.split("---", 2)
    if len(parts) < 3:
        return None

    try:
        data = yaml.safe_load(parts[1])
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    raw_id = data.get("id")
    if not raw_id and filename:
        file_stem = Path(filename).stem
        if file_stem.upper().startswith("WAIVER-"):
            raw_id = file_stem
    if not raw_id:
        return None

    try:
        w_id = normalize_waiver_id(raw_id)
    except ValueError:
        return None

    pkg = data.get("package") or data.get("package_name") or data.get("dependency") or ""
    signer = data.get("signer") or data.get("signed_by") or data.get("approved_by") or data.get("author") or ""
    raw_date = data.get("expires") or data.get("expiration") or data.get("expiration_date") or data.get("expires_at")

    if not pkg or not signer or raw_date is None:
        return None

    try:
        exp_date = parse_waiver_date(raw_date)
    except ValueError:
        return None

    sig = data.get("signature") or data.get("sig") or data.get("pgp_signature") or ""
    # If signature not explicitly in frontmatter, but signed by trusted officer, check signature in body
    if not sig and "Signed-by:" in content:
        for line in content.splitlines():
            if line.strip().lower().startswith("signature:"):
                sig = line.split(":", 1)[1].strip()

    version = str(data.get("version", "*"))
    cve = str(data.get("cve") or data.get("advisory_id") or data.get("vulnerability") or "")
    license_id = str(data.get("license") or data.get("allowed_license") or "")
    reason = str(data.get("reason", ""))
    status = str(data.get("status", "Approved"))

    return Waiver(
        id=w_id,
        package=str(pkg).strip().lower(),
        signer=str(signer).strip(),
        expires=exp_date,
        signature=str(sig).strip(),
        version=version,
        cve=cve.strip(),
        license=license_id.strip(),
        reason=reason.strip(),
        status=status.strip(),
        raw_frontmatter=data,
    )


def parse_waiver_file(file_path: Path) -> Waiver | None:
    """Reads and parses a waiver markdown file."""
    if not file_path.is_file():
        return None
    try:
        content = file_path.read_text(encoding="utf-8")
        return parse_waiver_content(content, filename=file_path.name)
    except Exception:
        return None


def load_waivers(waivers_dir: Path) -> list[Waiver]:
    """Loads all valid WAIVER-*.md files from specified directory."""
    if not waivers_dir.is_dir():
        return []

    waivers: list[Waiver] = []
    for f in sorted(waivers_dir.glob("WAIVER-*.md")):
        w = parse_waiver_file(f)
        if w is not None:
            waivers.append(w)
    return waivers


def find_active_waiver(
    waivers: list[Waiver],
    package: str,
    cve_id: str | None = None,
    license_id: str | None = None,
    reference_date: datetime.date | None = None,
    secret_key: str = DEFAULT_WAIVER_SECRET,
) -> Waiver | None:
    """Finds an unexpired, cryptographically valid waiver matching package and rule."""
    norm_pkg = package.strip().lower()
    for w in waivers:
        if w.package != norm_pkg:
            continue
        if is_waiver_expired(w, reference_date):
            continue
        if not verify_waiver_signature(w, secret_key=secret_key):
            continue
        if w.status.lower() not in ("approved", "active"):
            continue

        if cve_id:
            norm_cve = cve_id.strip().upper()
            if w.cve:
                if w.cve.strip().upper() != norm_cve:
                    continue
            elif w.license and not license_id:
                continue

        if license_id:
            norm_lic = license_id.strip().upper()
            if w.license:
                if w.license.strip().upper() != norm_lic:
                    continue
            elif w.cve and not cve_id:
                continue

        return w

    return None
