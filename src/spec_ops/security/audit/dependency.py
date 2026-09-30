"""Comprehensive dependency vulnerability and license policy audit runner."""

from __future__ import annotations

import datetime
from dataclasses import dataclass, field
from pathlib import Path

from ...config.loader import load_config
from ...config.models import SpecOpsConfig
from ..cve.osv_client import Vulnerability, audit_dependencies_cve
from ..licenses.policy import LicenseViolation, audit_dependencies_licenses, extract_repo_dependencies
from ..waivers import Waiver, load_waivers


@dataclass
class DependencyAuditReport:
    ok: bool
    vulnerabilities: list[Vulnerability] = field(default_factory=list)
    license_violations: list[LicenseViolation] = field(default_factory=list)
    active_waivers_used: list[Waiver] = field(default_factory=list)
    packages_scanned: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def unwaived_vulnerabilities(self) -> list[Vulnerability]:
        return [v for v in self.vulnerabilities if not v.waived]

    @property
    def unwaived_license_violations(self) -> list[LicenseViolation]:
        return [lv for lv in self.license_violations if not lv.waived]


def run_dependency_audit(
    repo_dir: Path,
    config: SpecOpsConfig | None = None,
    offline: bool = False,
    reference_date: datetime.date | None = None,
) -> DependencyAuditReport:
    """Executes full dependency audit: scans for High/Critical CVEs and enforces license allowlists."""
    effective_dir = repo_dir.resolve()
    effective_config = config or load_config(root_dir=effective_dir)

    deps = extract_repo_dependencies(effective_dir)
    packages_count = len(deps)

    allowed_licenses = None
    if effective_config.security and effective_config.security.licenses and effective_config.security.licenses.allowed:
        allowed_licenses = effective_config.security.licenses.allowed
    elif effective_config.security and effective_config.security.allowed_licenses:
        allowed_licenses = effective_config.security.allowed_licenses

    waivers_dir = effective_dir / "docs" / "project" / "compliance" / "waivers"
    all_waivers = {w.id: w for w in load_waivers(waivers_dir)}

    # Scan licenses
    license_violations = audit_dependencies_licenses(
        effective_dir,
        allowed_licenses=allowed_licenses,
        waivers_dir=waivers_dir,
        reference_date=reference_date,
    )

    # Scan CVEs
    vulnerabilities = audit_dependencies_cve(
        effective_dir,
        min_severity="HIGH",
        waivers_dir=waivers_dir,
        reference_date=reference_date,
        offline=offline,
    )

    # Collect waivers used
    waiver_ids_used = set()
    for lv in license_violations:
        if lv.waived and lv.waiver_id:
            waiver_ids_used.add(lv.waiver_id)
    for v in vulnerabilities:
        if v.waived and v.waiver_id:
            waiver_ids_used.add(v.waiver_id)

    active_waivers_used = [all_waivers[wid] for wid in sorted(waiver_ids_used) if wid in all_waivers]

    errors: list[str] = []
    unwaived_cves = [v for v in vulnerabilities if not v.waived]
    unwaived_lics = [lv for lv in license_violations if not lv.waived]

    for v in unwaived_cves:
        aliases_text = f" ({', '.join(v.aliases)})" if v.aliases else ""
        errors.append(
            f"Package '{v.package}' has {v.severity} vulnerability {v.advisory_id}{aliases_text} "
            f"(CVSS {v.cvss_score}, remediating version: {v.fixed_version})"
        )

    for lv in unwaived_lics:
        errors.append(
            f"Package '{lv.package}' has non-compliant license '{lv.license}'"
        )

    is_ok = len(unwaived_cves) == 0 and len(unwaived_lics) == 0

    return DependencyAuditReport(
        ok=is_ok,
        vulnerabilities=vulnerabilities,
        license_violations=license_violations,
        active_waivers_used=active_waivers_used,
        packages_scanned=packages_count,
        errors=errors,
    )
