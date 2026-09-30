"""PRD lifecycle, linting, and decomposition package for SpecOps."""

from .audit import DeepPRDAuditor, OutcomeAuditResult, calculate_outcome_coverage, run_deep_audit
from .decomposer import PRDDecomposer
from .discovery import interactive_new_prd
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
    "interactive_new_prd",
    "run_deep_audit",
]
