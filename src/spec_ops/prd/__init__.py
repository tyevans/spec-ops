"""PRD lifecycle, linting, and decomposition package for SpecOps."""

from .audit import DeepPRDAuditor, OutcomeAuditResult, calculate_outcome_coverage, run_deep_audit
from .decomposer import PRDDecomposer
from .discovery import interactive_new_prd
from .discovery_workflow import discover_prd, shape_prd
from .exporter import export_roadmap, render_roadmap_html, render_roadmap_svg
from .bdd_matrix import (
    BDDCoverageAuditor,
    BDDCoverageMatrix,
    BDDScenarioItem,
    StoryCoverageReport,
)
from .journey_map import CustomerJourneyReport, JourneyMapEngine, PainPointRecord, PersonaJourneyMap
from .lifecycle import PRDLifecycleManager
from .linter import PRDLinter
from .manager import PRDAuditResult, PRDManager
from .studio_state import PRDStudioSessionState, PRDSummary, PRDStudioStateManager
from .traceability import PersonaCoverageReport, PersonaLineageRecord, PersonaTraceabilityEngine

__all__ = [
    "BDDCoverageAuditor",
    "BDDCoverageMatrix",
    "BDDScenarioItem",
    "CustomerJourneyReport",
    "DeepPRDAuditor",
    "JourneyMapEngine",
    "OutcomeAuditResult",
    "PRDAuditResult",
    "PRDDecomposer",
    "PRDLifecycleManager",
    "PRDLinter",
    "PRDManager",
    "PRDStudioSessionState",
    "PRDStudioStateManager",
    "PRDSummary",
    "PainPointRecord",
    "PersonaCoverageReport",
    "PersonaJourneyMap",
    "PersonaLineageRecord",
    "PersonaTraceabilityEngine",
    "StoryCoverageReport",
    "calculate_outcome_coverage",
    "discover_prd",
    "export_roadmap",
    "interactive_new_prd",
    "render_roadmap_html",
    "render_roadmap_svg",
    "run_deep_audit",
    "shape_prd",
]
