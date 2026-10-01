"""Release engineering, customer-facing notes, and living changelog publishing."""

from __future__ import annotations

from .customer_notes import (
    CustomerReleaseNotesData,
    PersonaImpact,
    UATOutcome,
    build_customer_notes_data,
    generate_customer_release_notes,
    render_html_customer_notes,
    render_json_customer_notes,
    render_markdown_customer_notes,
)
from .velocity_heatmap import (
    FileChurnStat,
    TaskLeadTimeStat,
    VelocityHeatmapReport,
    analyze_velocity_and_churn,
    compute_file_churn,
    compute_velocity_metrics,
    generate_velocity_heatmap,
    render_velocity_html,
    render_velocity_json,
    render_velocity_markdown,
)

__all__ = [
    "CustomerReleaseNotesData",
    "FileChurnStat",
    "PersonaImpact",
    "TaskLeadTimeStat",
    "UATOutcome",
    "VelocityHeatmapReport",
    "analyze_velocity_and_churn",
    "build_customer_notes_data",
    "compute_file_churn",
    "compute_velocity_metrics",
    "generate_customer_release_notes",
    "generate_velocity_heatmap",
    "render_html_customer_notes",
    "render_json_customer_notes",
    "render_markdown_customer_notes",
    "render_velocity_html",
    "render_velocity_json",
    "render_velocity_markdown",
]
