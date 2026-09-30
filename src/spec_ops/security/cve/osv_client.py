"""OSV API client and CVE vulnerability auditing."""

from __future__ import annotations

import datetime
import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..licenses.policy import extract_repo_dependencies
from ..waivers import Waiver, find_active_waiver, load_waivers

OSV_QUERY_URL = "https://api.osv.dev/v1/query"


@dataclass
class Vulnerability:
    package: str
    version: str
    advisory_id: str
    aliases: list[str] = field(default_factory=list)
    cvss_score: float = 0.0
    severity: str = "UNKNOWN"
    fixed_version: str = "None"
    summary: str = ""
    waived: bool = False
    waiver_id: str = ""
    waiver_expires: str = ""


def parse_cvss_score(score_input: Any) -> float:
    """Extracts numeric CVSS score from float, int, or string."""
    if isinstance(score_input, (int, float)):
        return float(score_input)
    if isinstance(score_input, str):
        cleaned = score_input.strip()
        subbed = re.sub(r"^CVSS:[0-9.]+\/", "", cleaned)
        matches = re.findall(r"(\d+(?:\.\d+)?)", subbed)
        for m in reversed(matches):
            try:
                val = float(m)
                if 0.0 < val <= 10.0:
                    return val
            except ValueError:
                pass
        try:
            return float(cleaned)
        except ValueError:
            pass
    return 0.0


def classify_severity(cvss_score: float, severity_str: str = "") -> str:
    """Classifies severity into LOW, MODERATE, HIGH, or CRITICAL."""
    sev_upper = severity_str.strip().upper()
    if sev_upper in ("CRITICAL", "HIGH", "MODERATE", "MEDIUM", "LOW"):
        return "MEDIUM" if sev_upper == "MODERATE" else sev_upper

    if cvss_score >= 9.0:
        return "CRITICAL"
    if cvss_score >= 7.0:
        return "HIGH"
    if cvss_score >= 4.0:
        return "MEDIUM"
    if cvss_score > 0.0:
        return "LOW"
    return "UNKNOWN"


def _extract_fixed_version(item: dict[str, Any]) -> str:
    """Extracts minimum remediating / fixed version from affected ranges."""
    affected = item.get("affected", [])
    if isinstance(affected, list):
        for aff in affected:
            if not isinstance(aff, dict):
                continue
            ranges = aff.get("ranges", [])
            if isinstance(ranges, list):
                for r in ranges:
                    if not isinstance(r, dict):
                        continue
                    for ev in r.get("events", []):
                        if isinstance(ev, dict) and "fixed" in ev:
                            return str(ev["fixed"])
    return "None"


def parse_osv_vulnerability(item: dict[str, Any], package_name: str, version: str) -> Vulnerability:
    """Parses raw OSV or cache vulnerability item into Vulnerability model."""
    adv_id = str(item.get("id") or item.get("advisory_id") or "UNKNOWN")
    aliases = [str(a) for a in item.get("aliases", []) if a]
    summary = str(item.get("summary") or "")

    cvss_score = 0.0
    if "cvss_score" in item:
        cvss_score = parse_cvss_score(item["cvss_score"])
    elif "database_specific" in item and isinstance(item["database_specific"], dict):
        cvss_score = parse_cvss_score(item["database_specific"].get("cvss") or item["database_specific"].get("cvss_score"))
    elif "severity" in item and isinstance(item["severity"], list):
        for s in item["severity"]:
            if isinstance(s, dict):
                score_str = s.get("score")
                score_val = parse_cvss_score(score_str)
                if score_val > cvss_score:
                    cvss_score = score_val

    severity_hint = str(item.get("severity") or "")
    if not severity_hint and "database_specific" in item and isinstance(item["database_specific"], dict):
        severity_hint = str(item["database_specific"].get("severity") or "")
    if isinstance(item.get("severity"), list) and not severity_hint:
        for s in item["severity"]:
            if isinstance(s, dict) and "type" in s and s.get("score"):
                pass

    if cvss_score == 0.0:
        if severity_hint.upper() == "CRITICAL":
            cvss_score = 9.5
        elif severity_hint.upper() == "HIGH":
            cvss_score = 8.0
        elif severity_hint.upper() in ("MODERATE", "MEDIUM"):
            cvss_score = 5.5
        elif severity_hint.upper() == "LOW":
            cvss_score = 2.5

    severity = classify_severity(cvss_score, severity_hint)
    fixed_ver = str(item.get("fixed_version") or _extract_fixed_version(item))

    return Vulnerability(
        package=package_name,
        version=version,
        advisory_id=adv_id,
        aliases=aliases,
        cvss_score=cvss_score,
        severity=severity,
        fixed_version=fixed_ver,
        summary=summary,
    )


def query_osv_vulnerabilities(
    package_name: str,
    version: str,
    repo_dir: Path | None = None,
    offline: bool = False,
    timeout: int = 3,
) -> list[Vulnerability]:
    """Queries OSV or local vulnerability database cache for known package CVEs."""
    # Check local cache first
    if repo_dir:
        for candidate_name in ("docs/project/compliance/cve_cache.json", ".spec-ops/cve_cache.json"):
            cache_file = repo_dir / candidate_name
            if cache_file.is_file():
                try:
                    data = json.loads(cache_file.read_text(encoding="utf-8"))
                    packages_map = data.get("packages", data)
                    pkg_records = packages_map.get(package_name, [])
                    if pkg_records:
                        results = []
                        for rec in pkg_records:
                            rec_ver = rec.get("version", version)
                            if rec_ver in (version, "*") or not rec.get("version"):
                                results.append(parse_osv_vulnerability(rec, package_name, version))
                        return results
                except Exception:
                    pass

    if offline:
        return []

    # Query OSV public API
    payload = {
        "package": {"name": package_name, "ecosystem": "PyPI"},
        "version": version,
    }
    try:
        req = urllib.request.Request(
            OSV_QUERY_URL,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json", "User-Agent": "SpecOps-Audit/0.1.0"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            vulns = body.get("vulns", [])
            return [parse_osv_vulnerability(v, package_name, version) for v in vulns]
    except Exception:
        return []


def audit_dependencies_cve(
    repo_dir: Path,
    min_severity: str = "HIGH",
    waivers_dir: Path | None = None,
    reference_date: datetime.date | None = None,
    offline: bool = False,
) -> list[Vulnerability]:
    """Audits repository dependencies for High and Critical CVEs with waiver support."""
    w_dir = waivers_dir or (repo_dir / "docs" / "project" / "compliance" / "waivers")
    waivers = load_waivers(w_dir)
    deps = extract_repo_dependencies(repo_dir)

    target_severities = {"HIGH", "CRITICAL"} if min_severity.upper() in ("HIGH", "CRITICAL") else {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
    findings: list[Vulnerability] = []

    for pkg_name, pkg_ver, _ in deps:
        vulns = query_osv_vulnerabilities(pkg_name, pkg_ver, repo_dir=repo_dir, offline=offline)
        for v in vulns:
            if v.severity in target_severities or v.cvss_score >= 7.0:
                # Check for waiver matching advisory_id or aliases
                active_w = find_active_waiver(
                    waivers,
                    package=pkg_name,
                    cve_id=v.advisory_id,
                    reference_date=reference_date,
                )
                if not active_w:
                    for alias in v.aliases:
                        active_w = find_active_waiver(
                            waivers,
                            package=pkg_name,
                            cve_id=alias,
                            reference_date=reference_date,
                        )
                        if active_w:
                            break

                if active_w:
                    v.waived = True
                    v.waiver_id = active_w.id
                    v.waiver_expires = str(active_w.expires)
                else:
                    v.waived = False
                findings.append(v)

    return findings
