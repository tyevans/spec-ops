"""Diataxis documentation compiler, auditor, and site builder for SpecOps."""

from .auditor import DocsAuditor, check_diataxis_structure
from .builder import build_docs_site
from .cli_inspector import check_cli_drift
from .models import AuditReport, AuditViolation
from .snippet_tester import check_code_snippets

__all__ = [
    "DocsAuditor",
    "AuditReport",
    "AuditViolation",
    "build_docs_site",
    "check_cli_drift",
    "check_code_snippets",
    "check_diataxis_structure",
]
