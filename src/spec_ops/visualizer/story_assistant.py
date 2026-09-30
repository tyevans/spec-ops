"""Story assistant and Gherkin step autocompletion for SpecOps visualizer (ADR-0002 seam)."""

from __future__ import annotations

from ..prd.step_assistant import (
    BACKDOOR_PATTERNS,
    DEFAULT_FRONTDOOR_STEPS,
    accept_user_story,
    detect_backdoors,
    extract_frontdoor_steps,
    find_next_story_id,
)

__all__ = [
    "BACKDOOR_PATTERNS",
    "DEFAULT_FRONTDOOR_STEPS",
    "accept_user_story",
    "detect_backdoors",
    "extract_frontdoor_steps",
    "find_next_story_id",
]
