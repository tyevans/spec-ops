"""OSV client and CVE dependency vulnerability auditing."""

from .osv_client import (
    Vulnerability,
    audit_dependencies_cve,
    classify_severity,
    parse_cvss_score,
    query_osv_vulnerabilities,
)

__all__ = [
    "Vulnerability",
    "audit_dependencies_cve",
    "classify_severity",
    "parse_cvss_score",
    "query_osv_vulnerabilities",
]
