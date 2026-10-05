"""Software license policy enforcement and allowlist auditing."""

from __future__ import annotations

import datetime
import importlib.metadata
import json
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ...config.loader import load_config
from ..waivers import Waiver, find_active_waiver, load_waivers

STANDARD_PROFILES: dict[str, list[str]] = {
    "permissive": [
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "0BSD",
        "Unlicense",
        "Python-2.0",
        "CC0-1.0",
        "PSF-2.0",
        "MPL-2.0",
        "CNRI-Python",
    ],
    "commercial-saas": [
        "MIT",
        "Apache-2.0",
        "BSD-2-Clause",
        "BSD-3-Clause",
        "ISC",
        "0BSD",
        "Python-2.0",
        "PSF-2.0",
    ],
}

KNOWN_PACKAGE_LICENSES: dict[str, str] = {
    "annotated-types": "MIT",
    "click": "BSD-3-Clause",
    "colorama": "BSD-3-Clause",
    "coverage": "Apache-2.0",
    "dateparser": "BSD-3-Clause",
    "eventsource-py": "MIT",
    "hypothesis": "MPL-2.0",
    "mutmut": "BSD-3-Clause",
    "platformdirs": "MIT",
    "pluggy": "MIT",
    "pytest": "MIT",
    "pytest-bdd": "MIT",
    "python-dateutil": "BSD-3-Clause",
    "pyyaml": "MIT",
    "redstring": "MIT",
    "regex": "Apache-2.0",
    "rich": "MIT",
    "spec-ops": "MIT",
    "tzdata": "CC0-1.0",
}

LICENSE_SYNONYMS: dict[str, str] = {
    "mit": "MIT",
    "mit license": "MIT",
    "apache": "Apache-2.0",
    "apache 2.0": "Apache-2.0",
    "apache-2.0": "Apache-2.0",
    "apache license 2.0": "Apache-2.0",
    "apache software license": "Apache-2.0",
    "bsd": "BSD-3-Clause",
    "bsd license": "BSD-3-Clause",
    "bsd-3-clause": "BSD-3-Clause",
    "bsd 3-clause": "BSD-3-Clause",
    "bsd 3-clause license": "BSD-3-Clause",
    "bsd-2-clause": "BSD-2-Clause",
    "bsd 2-clause": "BSD-2-Clause",
    "isc": "ISC",
    "isc license": "ISC",
    "0bsd": "0BSD",
    "unlicense": "Unlicense",
    "python-2.0": "Python-2.0",
    "psf-2.0": "Python-2.0",
    "psfl": "Python-2.0",
    "psf": "Python-2.0",
    "python software foundation license": "Python-2.0",
    "cc0-1.0": "CC0-1.0",
    "mpl-2.0": "MPL-2.0",
    "mozilla public license 2.0": "MPL-2.0",
    "gpl-2.0": "GPL-2.0",
    "gplv2": "GPL-2.0",
    "gpl-3.0": "GPL-3.0",
    "gplv3": "GPL-3.0",
    "gnu general public license v3": "GPL-3.0",
    "agpl-3.0": "AGPL-3.0",
    "agplv3": "AGPL-3.0",
    "gnu affero general public license v3": "AGPL-3.0",
    "gnu affero general public license": "AGPL-3.0",
    "lgpl": "LGPL-3.0",
    "lgpl-2.1": "LGPL-2.1",
    "lgpl-3.0": "LGPL-3.0",
    "lgplv3": "LGPL-3.0",
    "gnu library or lesser general public license (lgpl)": "LGPL-3.0",
}


@dataclass
class LicenseViolation:
    package: str
    version: str
    license: str
    reason: str
    waived: bool = False
    waiver_id: str = ""
    waiver_expires: str = ""


def normalize_license(license_str: str) -> str:
    """Normalizes license string to standardized SPDX identifier where recognized."""
    if not license_str or not isinstance(license_str, str):
        return "UNKNOWN"
    cleaned = license_str.strip()
    lower = cleaned.lower()
    if lower in LICENSE_SYNONYMS:
        return LICENSE_SYNONYMS[lower]
    for key, val in LICENSE_SYNONYMS.items():
        if key in lower:
            return val
    return cleaned


def is_license_allowed(license_name: str, allowed_licenses: list[str]) -> bool:
    """Checks whether normalized license is permitted under allowlist."""
    norm = normalize_license(license_name).strip()
    allowed_set = {normalize_license(a).lower() for a in allowed_licenses}
    if norm.lower() in allowed_set:
        return True
    cleaned = re.sub(r"[\(\)]", "", norm)
    if " or " in cleaned.lower():
        parts = [p.strip() for p in re.split(r"\s+or\s+", cleaned, flags=re.IGNORECASE) if p.strip()]
        if parts:
            return any(is_license_allowed(p, allowed_licenses) for p in parts)
    if " and " in cleaned.lower():
        parts = [p.strip() for p in re.split(r"\s+and\s+", cleaned, flags=re.IGNORECASE) if p.strip()]
        if parts:
            return all(is_license_allowed(p, allowed_licenses) for p in parts)
    return False


def resolve_package_license(
    package_name: str,
    package_record: dict[str, Any] | None = None,
    repo_dir: Path | None = None,
) -> str:
    """Resolves license for package from lockfile record, local cache, metadata, or heuristics."""
    if package_record and isinstance(package_record, dict):
        raw = package_record.get("license")
        if raw and isinstance(raw, str):
            return normalize_license(raw)

    if repo_dir:
        for candidate_name in (
            "docs/project/compliance/licenses.json",
            ".spec-ops/licenses.json",
            ".specops/licenses.json",
        ):
            cache_file = repo_dir / candidate_name
            if cache_file.is_file():
                try:
                    data = json.loads(cache_file.read_text(encoding="utf-8"))
                    packages_map = data.get("packages", data)
                    if package_name in packages_map:
                        val = packages_map[package_name]
                        lic = val.get("license", val) if isinstance(val, dict) else str(val)
                        return normalize_license(lic)
                except Exception:
                    pass

    pkg_lower = package_name.lower()
    if pkg_lower in KNOWN_PACKAGE_LICENSES:
        return KNOWN_PACKAGE_LICENSES[pkg_lower]

    search_paths: list[str] | None = None
    if repo_dir:
        venv_paths = [str(p) for p in repo_dir.glob(".venv/lib/python*/site-packages") if p.is_dir()]
        if venv_paths:
            search_paths = venv_paths

    dist = None
    if search_paths:
        try:
            dists = list(importlib.metadata.distributions(name=package_name, path=search_paths))
            if dists:
                dist = dists[0]
        except Exception:
            pass

    if not dist:
        try:
            dist = importlib.metadata.distribution(package_name)
        except Exception:
            pass

    if dist:
        try:
            lic_expr = dist.metadata.get("License-Expression")
            if lic_expr and lic_expr.upper() != "UNKNOWN":
                return normalize_license(lic_expr)
            raw_lic = dist.metadata.get("License")
            if raw_lic and raw_lic.upper() not in ("UNKNOWN", "DUAL LICENSE"):
                return normalize_license(raw_lic)
            classifiers = dist.metadata.get_all("Classifier") or []
            for c in classifiers:
                if "License :: OSI Approved :: " in c:
                    return normalize_license(c.split("License :: OSI Approved :: ")[-1].strip())
            if raw_lic and raw_lic.upper() != "UNKNOWN":
                return normalize_license(raw_lic)
        except Exception:
            pass

    if "agpl" in pkg_lower:
        return "AGPL-3.0"
    if "gpl" in pkg_lower:
        return "GPL-3.0"

    return "UNKNOWN"


def extract_repo_dependencies(repo_dir: Path) -> list[tuple[str, str, dict[str, Any]]]:
    """Extracts package dependencies and metadata from uv.lock or pyproject.toml."""
    lockfile = repo_dir / "uv.lock"
    deps: list[tuple[str, str, dict[str, Any]]] = []

    if lockfile.is_file():
        try:
            data = tomllib.loads(lockfile.read_text(encoding="utf-8"))
            for pkg in data.get("package", []):
                if isinstance(pkg, dict) and "name" in pkg:
                    deps.append((str(pkg["name"]), str(pkg.get("version", "0.0.0")), pkg))
            if deps:
                return deps
        except Exception:
            pass

    pyproject = repo_dir / "pyproject.toml"
    if pyproject.is_file():
        try:
            data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
            raw_deps = data.get("project", {}).get("dependencies", [])
            for dep_str in raw_deps:
                m = re.match(r"^([a-zA-Z0-9._-]+)(?:==|>=|<=|~=|>|<)?([a-zA-Z0-9._-]+)?", str(dep_str))
                if m:
                    pkg_name = m.group(1)
                    pkg_ver = m.group(2) or "0.0.0"
                    deps.append((pkg_name, pkg_ver, {}))
        except Exception:
            pass

    return deps


def audit_dependencies_licenses(
    repo_dir: Path,
    allowed_licenses: list[str] | None = None,
    waivers_dir: Path | None = None,
    reference_date: datetime.date | None = None,
) -> list[LicenseViolation]:
    """Audits dependencies against license allowlist and unexpired policy waivers."""
    effective_allowed = allowed_licenses
    if effective_allowed is None:
        cfg = load_config(root_dir=repo_dir)
        if cfg.security and cfg.security.licenses and cfg.security.licenses.allowed:
            effective_allowed = cfg.security.licenses.allowed
        elif cfg.security and cfg.security.allowed_licenses:
            effective_allowed = cfg.security.allowed_licenses
        else:
            profile = (cfg.security and cfg.security.licenses and cfg.security.licenses.profile) or "permissive"
            effective_allowed = STANDARD_PROFILES.get(profile, STANDARD_PROFILES["permissive"])

    w_dir = waivers_dir or (repo_dir / "docs" / "project" / "compliance" / "waivers")
    waivers = load_waivers(w_dir)
    deps = extract_repo_dependencies(repo_dir)

    violations: list[LicenseViolation] = []
    for pkg_name, pkg_ver, pkg_record in deps:
        lic = resolve_package_license(pkg_name, pkg_record, repo_dir=repo_dir)
        if not is_license_allowed(lic, effective_allowed):
            active_w = find_active_waiver(
                waivers,
                package=pkg_name,
                license_id=lic,
                reference_date=reference_date,
            )
            if active_w:
                violations.append(
                    LicenseViolation(
                        package=pkg_name,
                        version=pkg_ver,
                        license=lic,
                        reason=f"Incompatible license '{lic}' waived by {active_w.id}",
                        waived=True,
                        waiver_id=active_w.id,
                        waiver_expires=str(active_w.expires),
                    )
                )
            else:
                violations.append(
                    LicenseViolation(
                        package=pkg_name,
                        version=pkg_ver,
                        license=lic,
                        reason=f"Incompatible license '{lic}' not in allowlist {effective_allowed}",
                        waived=False,
                    )
                )

    return violations
