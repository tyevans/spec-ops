"""PRD lifecycle, linting, and decomposition package for SpecOps."""

from .audit import DeepPRDAuditor, OutcomeAuditResult, calculate_outcome_coverage, run_deep_audit
from .decomposer import PRDDecomposer
from .discovery import interactive_new_prd
from .discovery_workflow import discover_prd, shape_prd
from .exporter import export_roadmap, render_roadmap_html, render_roadmap_svg
from .lifecycle import PRDLifecycleManager
from .linter import PRDLinter
from .manager import PRDAuditResult, PRDManager
from .traceability import PersonaCoverageReport, PersonaLineageRecord, PersonaTraceabilityEngine

__all__ = [
    "DeepPRDAuditor",
    "OutcomeAuditResult",
    "PRDAuditResult",
    "PRDDecomposer",
    "PRDLifecycleManager",
    "PRDLinter",
    "PRDManager",
    "PersonaCoverageReport",
    "PersonaLineageRecord",
    "PersonaTraceabilityEngine",
    "calculate_outcome_coverage",
    "discover_prd",
    "export_roadmap",
    "interactive_new_prd",
    "render_roadmap_html",
    "render_roadmap_svg",
    "run_deep_audit",
    "shape_prd",
]
