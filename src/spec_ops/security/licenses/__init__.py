"""Software license allowlist and compliance gating."""

from .policy import (
    STANDARD_PROFILES,
    LicenseViolation,
    audit_dependencies_licenses,
    is_license_allowed,
    normalize_license,
    resolve_package_license,
)

__all__ = [
    "STANDARD_PROFILES",
    "LicenseViolation",
    "audit_dependencies_licenses",
    "is_license_allowed",
    "normalize_license",
    "resolve_package_license",
]
