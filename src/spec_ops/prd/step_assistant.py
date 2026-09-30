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


def find_next_story_id(user_stories_dir: Path) -> tuple[str, int]:
    """Finds next sequential User Story ID across user story markdown files."""
    max_num = 0
    if user_stories_dir.exists():
        for p in user_stories_dir.rglob("*.md"):
            m = re.search(r"us-(\d+)", p.stem, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                if val > max_num:
                    max_num = val
    next_num = max_num + 1
    return f"US-{next_num:04d}", next_num


def accept_user_story(
    repo_root: Path,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Accepts a completed user story, validating INVEST criteria, no backdoors, and links to PRD."""
    title = str(data.get("title", "")).strip()
    if not title:
        return {
            "success": False,
            "error": "Validation Error",
            "message": "User story title is required.",
        }

    scenario = str(data.get("scenario") or data.get("content") or "").strip()
    if not scenario:
        return {
            "success": False,
            "error": "Validation Error",
            "message": "Gherkin scenario content is required.",
        }

    # ADR-0003: Check for backdoors in scenario
    for line in scenario.splitlines():
        line_clean = line.strip()
        if not line_clean:
            continue
        is_bd, warn, alt = detect_backdoors(line_clean)
        if is_bd:
            return {
                "success": False,
                "error": "Backdoor violation (ADR-0003)",
                "message": warn,
                "suggested_alt": alt,
                "offending_line": line_clean,
            }

    # ADR-0006: INVEST & Gherkin structure validation
    has_scenario = bool(re.search(r"\bScenario\s*:", scenario, re.IGNORECASE))
    has_steps = any(
        re.search(rf"\b{kw}\b", scenario, re.IGNORECASE)
        for kw in ("Given", "When", "Then")
    )
    if not (has_scenario and has_steps):
        return {
            "success": False,
            "error": "INVEST Criteria Failure (ADR-0006)",
            "message": (
                "Story scenario must satisfy INVEST criteria with explicit Gherkin "
                "scenarios ('Scenario: ... Given ... When ... Then')."
            ),
        }

    root = Path(repo_root).resolve()
    stories_dir = root / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)

    explicit_id = data.get("story_id") or data.get("id")
    if explicit_id:
        digits = re.findall(r"\d+", str(explicit_id))
        num = int(digits[-1]) if digits else 1
        num_str = f"{num:04d}"
        canonical_id = f"US-{num_str}"
    else:
        canonical_id, num = find_next_story_id(root / "docs" / "project" / "user_stories")
        num_str = f"{num:04d}"

    from .studio import serialize_prd_document, slugify

    slug = slugify(title)
    filename = f"us-{num_str}-{slug}.md"
    target_path = stories_dir / filename

    persona = str(data.get("persona", "Taylor")).strip() or "Taylor"
    feature = str(data.get("feature", "FEAT-BDD-02")).strip() or "FEAT-BDD-02"
    governing_prd = str(data.get("governing_prd", "PRD-0003")).strip() or "PRD-0003"
    i_want = str(data.get("i_want", f"implement {title.lower()}")).strip()
    so_that = str(data.get("so_that", "deliver verifiable customer value")).strip()
    created_date = str(data.get("created", "2026-09-29")).strip()

    frontmatter = {
        "id": num_str,
        "title": title,
        "status": "Accepted",
        "created": created_date,
        "persona": persona,
        "feature": feature,
        "governing_prd": governing_prd,
    }

    body = (
        f"# {canonical_id} — {title}\n\n"
        f"## Governing PRD\n"
        f"- [`{governing_prd}`](../../product/accepted/{slugify(governing_prd)}.md)\n\n"
        f"## User Story\n\n"
        f"**As an** {persona},\n"
        f"**I want** {i_want},\n"
        f"**So that** {so_that}.\n\n"
        f"## Acceptance Criteria\n\n"
        f"```gherkin\n"
        f"{scenario}\n"
        f"```\n\n"
        f"## Rationale & Compelling Value\n"
        f"Enforces ADR-0003 (Blackbox Frontdoor Verification) and ADR-0006 (BDD User Stories) "
        f"upstream during specification time.\n"
    )

    full_content = serialize_prd_document(frontmatter, body)
    target_path.write_text(full_content, encoding="utf-8")

    # Link story to governing PRD if found
    linked_prd_path = None
    product_dir = root / "docs" / "project" / "product"
    if product_dir.exists():
        clean_prd = governing_prd.upper().strip()
        for prd_file in product_dir.rglob("*.md"):
            m = re.search(r"prd-(\d+)", prd_file.stem, re.IGNORECASE)
            if m and (clean_prd in prd_file.name.upper() or f"PRD-{int(m.group(1)):04d}" == clean_prd):
                content = prd_file.read_text(encoding="utf-8")
                story_ref = f"- `{canonical_id}`"
                if story_ref not in content and canonical_id not in content:
                    if "## Linked User Stories" in content:
                        parts = content.split("## Linked User Stories", 1)
                        content = f"{parts[0]}## Linked User Stories\n\n{story_ref}\n{parts[1].lstrip()}"
                    else:
                        content += f"\n\n## Linked User Stories\n\n{story_ref}\n"
                    prd_file.write_text(content, encoding="utf-8")
                linked_prd_path = str(prd_file.relative_to(root))
                break

    rel_path = str(target_path.relative_to(root))
    return {
        "success": True,
        "story_id": canonical_id,
        "title": title,
        "file_path": rel_path,
        "absolute_path": str(target_path),
        "governing_prd": governing_prd,
        "linked_prd_file": linked_prd_path,
        "message": f"Accepted user story {canonical_id} at {rel_path}",
    }

