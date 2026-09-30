"""Step fixture assistant, public frontdoor autocomplete, and backdoor detector."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

BACKDOOR_PATTERNS = [
    (r"\bdatabase\s+table\b", "Direct database table manipulation"),
    (r"\bhas\s+record\b", "Direct database record state assertion"),
    (r"\bmock(?:ed|ing)?\b", "Private mock or monkeypatch backdoor"),
    (r"\bdirect\s+state\b", "Direct state manipulation"),
    (r"\binsert\s+into\b", "Raw SQL insertion"),
    (r"\bselect\s+.*\s+from\b", "Raw SQL query"),
    (r"\binternal\s+state\b", "Internal private state access"),
    (r"\bprivate\s+internals?\b", "Private internal state tampering"),
    (r"\bprivate\s+attributes?\b", "Private object attribute inspection"),
    (r"\bbackdoor\b", "Explicit backdoor usage"),
]

DEFAULT_FRONTDOOR_STEPS: list[dict[str, Any]] = [
    {
        "pattern": "Given a project initialized with SpecOps",
        "domain": "CLI / Setup",
        "type": "Given",
        "example": "Given a project initialized with SpecOps",
    },
    {
        "pattern": "Given the standalone visualizer is open in a browser",
        "domain": "Web / UI",
        "type": "Given",
        "example": "Given the standalone visualizer is open in a browser",
    },
    {
        "pattern": "Given an accepted PRD with linked user stories",
        "domain": "Backlog",
        "type": "Given",
        "example": "Given an accepted PRD with linked user stories",
    },
    {
        "pattern": "When Taylor navigates to the \"PRDs & Features\" tab",
        "domain": "Web / UI",
        "type": "When",
        "example": "When Taylor navigates to the \"PRDs & Features\" tab and clicks \"New PRD\"",
    },
    {
        "pattern": "When Taylor clicks \"Save PRD Draft\"",
        "domain": "Web / UI",
        "type": "When",
        "example": "When Taylor clicks \"Save PRD Draft\"",
    },
    {
        "pattern": "When Taylor updates the problem statement in the form editor",
        "domain": "Web / UI",
        "type": "When",
        "example": "When Taylor updates the problem statement in the form editor",
    },
    {
        "pattern": "When the architect runs \"spec-ops spike graduate\"",
        "domain": "CLI / Spike",
        "type": "When",
        "example": "When the architect runs \"spec-ops spike graduate SPIKE-0002 --result proven\"",
    },
    {
        "pattern": "Then a new Markdown file is created at {path}",
        "domain": "Filesystem",
        "type": "Then",
        "example": "Then a new Markdown file is created at \"docs/project/product/idea/prd-0002.md\"",
    },
    {
        "pattern": "Then the editor displays a validation alert",
        "domain": "Web / UI",
        "type": "Then",
        "example": "Then the editor displays a validation alert highlighting the missing mandatory sections",
    },
    {
        "pattern": "Then clicking \"Commit Specification\" records the changes",
        "domain": "Git / Versioning",
        "type": "Then",
        "example": "Then clicking \"Commit Specification\" records the changes directly to the active feature branch",
    },
]


def detect_backdoors(step_text: str) -> tuple[bool, str, str]:
    """Detects private backdoor testing patterns in violation of ADR-0003."""
    lower_text = step_text.lower().strip()

    for pattern, rationale in BACKDOOR_PATTERNS:
        if re.search(pattern, lower_text):
            warning = (
                "Backdoor violation (ADR-0003): Tests must exercise public frontdoors. "
                "Direct state manipulation is prohibited."
            )
            # Suggest compliant public frontdoor alternatives based on pattern
            if "table" in lower_text or "record" in lower_text or "sql" in lower_text:
                alternative = (
                    "Initialize data via public CLI commands (e.g. 'Given a project initialized with SpecOps') "
                    "or authenticated public HTTP API calls."
                )
            elif "mock" in lower_text:
                alternative = (
                    "Use public environment configuration or test doubles through public interfaces "
                    "rather than private monkeypatching."
                )
            else:
                alternative = "Exercise observable behaviour via public CLI, HTTP, or UI entry points."

            return True, warning, alternative

    return False, "", ""


def extract_frontdoor_steps(
    repo_root: Path | None = None,
    query: str | None = None,
) -> list[dict[str, Any]]:
    """Extracts registered and dynamically discovered public frontdoor steps."""
    steps = list(DEFAULT_FRONTDOOR_STEPS)
    seen_patterns = {s["pattern"].lower() for s in steps}

    if repo_root:
        tests_dir = Path(repo_root) / "tests"
        if tests_dir.exists():
            for p in sorted(tests_dir.rglob("test_bdd_*.py")):
                try:
                    content = p.read_text(encoding="utf-8")
                    matches = re.findall(
                        r'@(given|when|then)\(\s*["\']([^"\']+)["\']\s*\)',
                        content,
                        re.IGNORECASE,
                    )
                    for step_type, pattern_str in matches:
                        clean_pattern = f"{step_type.capitalize()} {pattern_str.strip()}"
                        if clean_pattern.lower() not in seen_patterns:
                            seen_patterns.add(clean_pattern.lower())
                            steps.append({
                                "pattern": clean_pattern,
                                "domain": "Test Fixtures",
                                "type": step_type.capitalize(),
                                "example": clean_pattern,
                                "source_file": str(p.name),
                            })
                except Exception:
                    pass

    if query:
        q_lower = query.lower().strip()
        filtered = [s for s in steps if q_lower in s["pattern"].lower() or q_lower in s.get("domain", "").lower()]
        return filtered

    return steps
