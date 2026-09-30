"""Architectural Decision Record (ADR) management and supersession package."""

from .supersede import (
    ADRNotFoundError,
    CircularSupersessionError,
    SupersedeResult,
    discover_superseded_adrs,
    find_adr_file,
    find_tasks_citing_adr,
    normalize_adr_id,
    supersede_adr,
    update_registry_supersession,
)

__all__ = [
    "ADRNotFoundError",
    "CircularSupersessionError",
    "SupersedeResult",
    "discover_superseded_adrs",
    "find_adr_file",
    "find_tasks_citing_adr",
    "normalize_adr_id",
    "supersede_adr",
    "update_registry_supersession",
]
