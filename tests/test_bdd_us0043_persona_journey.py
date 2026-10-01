"""BDD step definitions for US-0043: Interactive Persona Customer Journey Map Visualizer."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from spec_ops.scaffold.init import init_project

scenarios("features/us_0043_persona_journey.feature")


@pytest.fixture
def bdd_context(tmp_path: Path) -> dict[str, Any]:
    init_project(tmp_path, name="JourneyMapBDD")
    return {
        "root": tmp_path,
        "res": None,
        "html": "",
    }


def _run_cli(root: Path, cmd_str: str) -> subprocess.CompletedProcess[str]:
    # Strip prefix 'spec-ops '
    args = cmd_str.split()[1:] if cmd_str.startswith("spec-ops ") else cmd_str.split()
    return subprocess.run(
        [sys.executable, "-m", "spec_ops.cli.main", *args],
        cwd=str(root),
        capture_output=True,
        text=True,
    )


@given(parsers.parse('a project repository with persona "{persona_name}" having {count:d} defined pain points'))
def setup_repo_with_persona_and_pain_points(bdd_context: dict[str, Any], persona_name: str, count: int) -> None:
    root = bdd_context["root"]
    personas_file = root / "docs" / "project" / "user_stories" / "PERSONAS.md"
    personas_file.parent.mkdir(parents=True, exist_ok=True)

    pain_points = [
        "High friction and terminal-command intimidation when collaborating on git-based specifications.",
        "Disconnect between green CI test runs and actual customer-ready business value.",
        "Double-entry overhead translating between git repositories and executive roadmaps.",
    ][:count]

    pain_points_md = "\n".join(f"  - {pp}" for pp in pain_points)
    content = f"""# SpecOps User Personas

Archetypes representing contributors and users.

---

## 5. {persona_name} — The Product Manager
- **Role**: Product manager, business analyst, or domain expert.
- **Pain Points**:
{pain_points_md}
- **Goals with SpecOps**:
  - Clear user acceptance testing workflows.
"""
    personas_file.write_text(content, encoding="utf-8")

    # Create accepted PRD
    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0003-web-studio.md").write_text(
        f"""---
id: '0003'
title: Product Discovery Web Studio
status: Accepted
target_persona: {persona_name}
component: prd
---

# PRD-0003: Product Discovery Web Studio
""",
        encoding="utf-8",
    )

    # Create accepted user story linked to pain point 1
    stories_dir = root / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0043-web-studio.md").write_text(
        f"""---
id: '0043'
title: Interactive Web-Based PRD Studio
status: Accepted
persona: {persona_name}
governing_prd: PRD-0003
pain_point: 1
---

# US-0043 — Interactive Web-Based PRD Studio
## Rationale
Eliminates terminal-command intimidation.
""",
        encoding="utf-8",
    )


@when(parsers.parse('the product lead runs "{command}"'))
def product_lead_runs_command(bdd_context: dict[str, Any], command: str) -> None:
    res = _run_cli(bdd_context["root"], command)
    bdd_context["res"] = res


@then("a journey coverage report is generated")
def journey_coverage_report_is_generated(bdd_context: dict[str, Any]) -> None:
    res = bdd_context["res"]
    assert res is not None
    assert res.returncode == 0, f"Command failed with stderr:\n{res.stderr}\nstdout:\n{res.stdout}"
    output = res.stdout
    assert "Customer Journey Map" in output or "Journey Coverage" in output
    assert "Coverage:" in output or "Coverage" in output


@then("identifies which pain points have linked accepted stories and which remain unaddressed")
def identifies_addressed_and_unaddressed_pain_points(bdd_context: dict[str, Any]) -> None:
    res = bdd_context["res"]
    assert res is not None
    output = res.stdout
    assert "Addressed" in output
    assert "Unaddressed" in output
    assert "US-0043" in output


@given("an accepted PRD with mapped persona user stories")
def accepted_prd_with_mapped_user_stories(bdd_context: dict[str, Any]) -> None:
    root = bdd_context["root"]
    personas_file = root / "docs" / "project" / "user_stories" / "PERSONAS.md"
    personas_file.parent.mkdir(parents=True, exist_ok=True)
    personas_file.write_text(
        """# SpecOps User Personas

---

## 1. Taylor — The Product Manager
- **Role**: Product manager.
- **Pain Points**:
  - High friction and terminal intimidation with git.
  - Disconnect between CI and business acceptance.
""",
        encoding="utf-8",
    )

    prd_dir = root / "docs" / "project" / "product" / "accepted"
    prd_dir.mkdir(parents=True, exist_ok=True)
    (prd_dir / "prd-0003-uat.md").write_text(
        """---
id: '0003'
title: Product Discovery and UAT Studio
status: Accepted
target_persona: Taylor
component: prd
---

# PRD-0003: Product Discovery
""",
        encoding="utf-8",
    )

    stories_dir = root / "docs" / "project" / "user_stories" / "accepted"
    stories_dir.mkdir(parents=True, exist_ok=True)
    (stories_dir / "us-0043-uat.md").write_text(
        """---
id: '0043'
title: Low-Code Gherkin Assistant
status: Accepted
persona: Taylor
governing_prd: PRD-0003
pain_point: 1
---

# US-0043 — Low-Code Assistant
""",
        encoding="utf-8",
    )


@when(parsers.parse('the user executes "{command}"'))
def user_executes_command(bdd_context: dict[str, Any], command: str) -> None:
    res = _run_cli(bdd_context["root"], command)
    bdd_context["res"] = res


@then("a standalone HTML journey map is produced")
def standalone_html_journey_map_produced(bdd_context: dict[str, Any]) -> None:
    res = bdd_context["res"]
    assert res is not None
    assert res.returncode == 0, f"Command failed with stderr:\n{res.stderr}\nstdout:\n{res.stdout}"
    root = bdd_context["root"]
    html_file = root / "dist" / "journey" / "customer-journey-map.html"
    assert html_file.is_file(), f"Expected HTML file at {html_file}"
    html_content = html_file.read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in html_content
    assert "Customer Journey Map" in html_content
    bdd_context["html"] = html_content


@then("includes verifiable coverage metrics")
def includes_verifiable_coverage_metrics(bdd_context: dict[str, Any]) -> None:
    html_content = bdd_context["html"]
    assert 'meta name="spec-ops:report-type" content="customer-journey-map"' in html_content
    assert re.search(r'meta name="spec-ops:journey-coverage" content="\d+(\.\d+)?"', html_content)
    assert re.search(r'meta name="spec-ops:total-pain-points" content="\d+"', html_content)
    assert re.search(r'meta name="spec-ops:addressed-pain-points" content="\d+"', html_content)
