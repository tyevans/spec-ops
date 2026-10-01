"""Supply-chain lockfile integrity sentinel and attestation audit logger (ADR-0018, US-0111)."""

from __future__ import annotations

import hashlib
import json
import tomllib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .lockfile import inspect_lockfile


@dataclass
class LockfileAttestation:
    """Structured attestation record for supply-chain lockfile integrity."""

    timestamp: str
    lockfile_sha256: str
    pyproject_sha256: str
    package_count: int
    is_valid: bool
    discrepancies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializes attestation record to a structured dictionary."""
        return {
            "timestamp": self.timestamp,
            "lockfile_sha256": self.lockfile_sha256,
            "pyproject_sha256": self.pyproject_sha256,
            "package_count": self.package_count,
            "is_valid": self.is_valid,
            "discrepancies": list(self.discrepancies),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LockfileAttestation:
        """Constructs an attestation record from a dictionary."""
        return cls(
            timestamp=str(data.get("timestamp", "")),
            lockfile_sha256=str(data.get("lockfile_sha256", "")),
            pyproject_sha256=str(data.get("pyproject_sha256", "")),
            package_count=int(data.get("package_count", 0)),
            is_valid=bool(data.get("is_valid", False)),
            discrepancies=list(data.get("discrepancies", [])),
        )


@dataclass
class LockfileIntegrityReport:
    """Outcome of supply-chain lockfile verification against baseline attestations."""

    is_clean: bool
    current_digest: str
    attested_digest: str | None
    discrepancies: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializes integrity verification report to a dictionary."""
        return {
            "is_clean": self.is_clean,
            "current_digest": self.current_digest,
            "attested_digest": self.attested_digest,
            "discrepancies": list(self.discrepancies),
        }

    def summary(self) -> str:
        """Renders human-readable summary of integrity status."""
        if self.is_clean:
            curr = self.current_digest[:16] if self.current_digest else "empty"
            return f"✅ Lockfile integrity verified: digest matches recorded attestation ({curr})."
        lines = ["❌ Supply-chain lockfile tampering detected:"]
        for d in self.discrepancies:
            lines.append(f"   - {d}")
        return "\n".join(lines)


def compute_file_sha256(path: Path) -> str:
    """Calculates canonical SHA-256 digest of a target file."""
    if not path.is_file():
        return ""
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


class SupplyChainSentinel:
    """Incremental supply-chain lockfile integrity sentinel and attestation logger."""

    def __init__(self, repo_root: Path | str | None = None) -> None:
        self.repo_root = Path(repo_root).resolve() if repo_root is not None else Path.cwd().resolve()

    @staticmethod
    def compute_digests(repo_root: Path | str) -> tuple[str, str]:
        """Computes canonical SHA-256 digests over uv.lock and pyproject.toml."""
        root = Path(repo_root).resolve()
        lock_sha = compute_file_sha256(root / "uv.lock")
        pyp_sha = compute_file_sha256(root / "pyproject.toml")
        return lock_sha, pyp_sha

    @staticmethod
    def generate_attestation(repo_root: Path | str) -> LockfileAttestation:
        """Generates a structured attestation record for current lockfile state."""
        root = Path(repo_root).resolve()
        lock_file = root / "uv.lock"
        pyp_file = root / "pyproject.toml"

        lock_sha, pyp_sha = SupplyChainSentinel.compute_digests(root)
        discrepancies: list[str] = []
        package_count = 0
        is_valid = True

        if not lock_file.is_file():
            is_valid = False
            discrepancies.append(f"Lockfile not found at {lock_file}")
        else:
            try:
                data = tomllib.loads(lock_file.read_text(encoding="utf-8"))
                pkgs = data.get("package", [])
                if isinstance(pkgs, list):
                    package_count = len(pkgs)
            except Exception as exc:
                is_valid = False
                discrepancies.append(f"Failed to parse lockfile TOML: {exc}")

            res = inspect_lockfile(lock_file)
            if not res.valid:
                is_valid = False
                discrepancies.extend(res.errors)

        if not pyp_file.is_file():
            is_valid = False
            discrepancies.append(f"pyproject.toml not found at {pyp_file}")

        now_iso = datetime.now(timezone.utc).isoformat()
        return LockfileAttestation(
            timestamp=now_iso,
            lockfile_sha256=lock_sha,
            pyproject_sha256=pyp_sha,
            package_count=package_count,
            is_valid=is_valid,
            discrepancies=discrepancies,
        )

    @staticmethod
    def record_attestation(
        repo_root: Path | str,
        attestation: LockfileAttestation | None = None,
    ) -> Path:
        """Appends structured attestation record to .specops/lockfile_attestations.jsonl."""
        root = Path(repo_root).resolve()
        if attestation is None:
            attestation = SupplyChainSentinel.generate_attestation(root)

        specops_dir = root / ".specops"
        specops_dir.mkdir(parents=True, exist_ok=True)
        log_file = specops_dir / "lockfile_attestations.jsonl"

        with log_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(attestation.to_dict()) + "\n")

        return log_file

    @staticmethod
    def verify_integrity(repo_root: Path | str) -> LockfileIntegrityReport:
        """Verifies active lockfile against recorded baseline attestation."""
        root = Path(repo_root).resolve()
        current_digest, _ = SupplyChainSentinel.compute_digests(root)
        lock_file = root / "uv.lock"

        if not lock_file.is_file():
            return LockfileIntegrityReport(
                is_clean=False,
                current_digest=current_digest,
                attested_digest=None,
                discrepancies=["Unauthorized supply-chain modification: uv.lock not found"],
            )

        log_file = root / ".specops" / "lockfile_attestations.jsonl"
        if not log_file.is_file():
            return LockfileIntegrityReport(
                is_clean=False,
                current_digest=current_digest,
                attested_digest=None,
                discrepancies=[
                    "Unauthorized supply-chain modification: no baseline attestation recorded in .specops/lockfile_attestations.jsonl"
                ],
            )

        raw_content = log_file.read_text(encoding="utf-8")
        lines = [line.strip() for line in raw_content.splitlines() if line.strip()]
        if not lines:
            return LockfileIntegrityReport(
                is_clean=False,
                current_digest=current_digest,
                attested_digest=None,
                discrepancies=[
                    "Unauthorized supply-chain modification: no attestation entries found in .specops/lockfile_attestations.jsonl"
                ],
            )

        try:
            latest_record = LockfileAttestation.from_dict(json.loads(lines[-1]))
        except Exception as exc:
            return LockfileIntegrityReport(
                is_clean=False,
                current_digest=current_digest,
                attested_digest=None,
                discrepancies=[f"Unauthorized supply-chain modification: corrupted attestation record: {exc}"],
            )

        attested_digest = latest_record.lockfile_sha256
        discrepancies: list[str] = []

        if current_digest != attested_digest:
            discrepancies.append(
                f"Unauthorized supply-chain modification: lockfile digest mismatch "
                f"(current: {current_digest}, attested: {attested_digest})"
            )

        if not latest_record.is_valid:
            discrepancies.extend(latest_record.discrepancies)

        return LockfileIntegrityReport(
            is_clean=len(discrepancies) == 0,
            current_digest=current_digest,
            attested_digest=attested_digest,
            discrepancies=discrepancies,
        )


def handle_audit_lockfile(args: Any, config: Any = None) -> int:
    """CLI handler for 'spec-ops security audit-lockfile'."""
    import sys

    repo_root = getattr(config, "root_dir", Path.cwd()) if config else Path.cwd()
    if getattr(args, "path", None):
        repo_root = Path(args.path).resolve()

    do_record = getattr(args, "record", False)
    do_verify = getattr(args, "verify", False)
    as_json = getattr(args, "json", False)

    # If neither --record nor --verify is explicitly requested, default to verify
    if not do_record and not do_verify:
        do_verify = True

    if do_record:
        attestation = SupplyChainSentinel.generate_attestation(repo_root)
        log_path = SupplyChainSentinel.record_attestation(repo_root, attestation)
        if not do_verify:
            if as_json:
                print(json.dumps(attestation.to_dict(), indent=2))
            else:
                try:
                    rel = log_path.relative_to(repo_root)
                except ValueError:
                    rel = log_path
                print(f"✅ Recorded lockfile attestation to {rel} (SHA-256: {attestation.lockfile_sha256[:16]}...)")
            return 0

    if do_verify:
        report = SupplyChainSentinel.verify_integrity(repo_root)
        if as_json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            if report.is_clean:
                print(report.summary())
            else:
                print(report.summary(), file=sys.stderr)
        return 0 if report.is_clean else 1

    return 0
