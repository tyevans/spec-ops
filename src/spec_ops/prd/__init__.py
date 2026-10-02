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
from .lint_api import dispatch_lint_api_request, lint_prd_api
from .lint_engine import (
    LineLevelSuggestion,
    PRDLintDiagnostic,
    PRDLintEngine,
    PRDLintReport,
)
from .linter import PRDLinter
from .studio_api import dispatch_studio_api_request
from .studio_runner import launch_prd_studio
from .studio_state import PRDStudioSessionState, PRDSummary, PRDStudioStateManager
from .studio_ui import STUDIO_COMPONENT_STORIES, render_studio_html
from .traceability import PersonaCoverageReport, PersonaLineageRecord, PersonaTraceabilityEngine

__all__ = [
    "BDDCoverageAuditor",
    "BDDCoverageMatrix",
    "BDDScenarioItem",
    "CustomerJourneyReport",
    "DeepPRDAuditor",
    "JourneyMapEngine",
    "LineLevelSuggestion",
    "OutcomeAuditResult",
    "PRDAuditResult",
    "PRDDecomposer",
    "PRDLifecycleManager",
    "PRDLintDiagnostic",
    "PRDLintEngine",
    "PRDLintReport",
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
    "STUDIO_COMPONENT_STORIES",
    "StoryCoverageReport",
    "calculate_outcome_coverage",
    "discover_prd",
    "dispatch_lint_api_request",
    "dispatch_studio_api_request",
    "export_roadmap",
    "interactive_new_prd",
    "launch_prd_studio",
    "lint_prd_api",
    "render_roadmap_html",
    "render_roadmap_svg",
    "run_deep_audit",
    "shape_prd",
]
