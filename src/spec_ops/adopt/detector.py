"""Detection, inspection, and conflict resolution for pre-existing documentation systems."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DocSystemInspection:
    """Findings from inspecting a brownfield repository's documentation and CI."""

    has_mkdocs: bool = False
    mkdocs_file: Path | None = None
    has_sphinx: bool = False
    sphinx_file: Path | None = None
    conflicting_workflows: list[Path] = field(default_factory=list)
    guidance: list[str] = field(default_factory=list)


def inspect_target_doc_systems(target_dir: Path) -> DocSystemInspection:
    """Inspects target directory for pre-existing documentation tools and conflicting deployment workflows."""
    inspection = DocSystemInspection()

    # 1. Detect MkDocs
    for candidate in ("mkdocs.yml", "mkdocs.yaml"):
        p = target_dir / candidate
        if p.exists() and p.is_file():
            inspection.has_mkdocs = True
            inspection.mkdocs_file = p
            inspection.guidance.append(
                f"Detected pre-existing MkDocs configuration at '{candidate}'."
            )
            break

    # 2. Detect Sphinx
    for candidate in ("docs/conf.py", "conf.py"):
        p = target_dir / candidate
        if p.exists() and p.is_file():
            inspection.has_sphinx = True
            inspection.sphinx_file = p
            inspection.guidance.append(
                f"Detected pre-existing Sphinx configuration at '{candidate}'."
            )
            break

    # 3. Detect conflicting GitHub Pages workflows
    workflows_dir = target_dir / ".github" / "workflows"
    if workflows_dir.exists() and workflows_dir.is_dir():
        for wf in sorted(workflows_dir.glob("*.yml")) + sorted(workflows_dir.glob("*.yaml")):
            if wf.name == "deploy-pages.yml":
                continue
            try:
                content = wf.read_text(encoding="utf-8")
            except Exception:
                continue

            has_pages_concurrency = bool(re.search(r"concurrency:\s*\n\s*group:\s*[\"']?pages[\"']?", content))
            has_deploy_pages = "actions/deploy-pages" in content or "upload-pages-artifact" in content

            if has_pages_concurrency or has_deploy_pages:
                inspection.conflicting_workflows.append(wf)
                rel_path = wf.relative_to(target_dir).as_posix()
                inspection.guidance.append(
                    f"Detected conflicting GitHub Pages deployment workflow at '{rel_path}' (concurrency group 'pages')."
                )

    if inspection.conflicting_workflows:
        inspection.guidance.append(
            "Actionable Guidance: Multiple GitHub Pages deployment workflows can cause deployment collisions. "
            "To bridge living visualizer into existing site or retire legacy workflow, consider using "
            "'--deconflict-workflow' to namespace concurrency groups or retire the legacy workflow."
        )

    if inspection.has_mkdocs:
        inspection.guidance.append(
            "Bridging Guidance: You can link the SpecOps 2D visualizer by adding a navigation entry "
            "to '/visualizer/' in your 'mkdocs.yml' and hosting the visualizer artifact at 'site/visualizer/'."
        )

    return inspection


def deconflict_pages_workflows(target_dir: Path) -> list[Path]:
    """Deconflicts legacy GitHub Pages workflows by namespacing conflicting concurrency groups."""
    inspection = inspect_target_doc_systems(target_dir)
    modified: list[Path] = []

    for wf in inspection.conflicting_workflows:
        try:
            content = wf.read_text(encoding="utf-8")
            # Replace concurrency group 'pages' with legacy namespace
            new_content = re.sub(
                r'(group:\s*["\']?)pages(["\']?)',
                r"\1legacy-pages\2",
                content,
            )
            if new_content != content:
                wf.write_text(new_content, encoding="utf-8")
                modified.append(wf)
        except Exception:
            continue

    return modified
