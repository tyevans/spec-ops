"""Bounded-context Diataxis documentation scaffolding for SpecOps."""

from __future__ import annotations

import re
from pathlib import Path

_BC_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


class DocumentationExistsError(Exception):
    """Raised when bounded context documentation already exists and force=False."""


class InvalidBoundedContextError(ValueError):
    """Raised when bounded context name fails validation."""


def validate_bc_name(bc: str) -> str:
    """Validates that a bounded context identifier is safe and non-empty.

    Rejects path traversal (slashes, backslashes, double dots, null bytes).
    """
    if not bc or not isinstance(bc, str):
        raise InvalidBoundedContextError("Bounded context name cannot be empty.")
    clean = bc.strip(" \t\r\n").lower()
    if not clean:
        raise InvalidBoundedContextError("Bounded context name cannot be empty.")
    if "/" in clean or "\\" in clean or ".." in clean or "\x00" in clean:
        raise InvalidBoundedContextError(
            f"Invalid bounded context name '{bc}': contains path traversal characters."
        )
    if not _BC_PATTERN.match(clean):
        raise InvalidBoundedContextError(
            f"Invalid bounded context name '{bc}': must match pattern ^[a-zA-Z0-9_-]+$."
        )
    return clean


def normalize_title(bc: str, title: str | None = None) -> str:
    """Returns cleaned title or humanized bounded context name."""
    if title and title.strip():
        return title.strip()
    return bc.replace("-", " ").replace("_", " ").title()


def get_visualizer_deep_link(bc: str, relative_prefix: str = "../../") -> str:
    """Constructs visualizer deep link with query focus and hash tab/focus."""
    clean_bc = validate_bc_name(bc)
    return f"{relative_prefix}visualizer/?focus={clean_bc}#tab=canvas&focus={clean_bc}"


def get_quadrant_paths(root_dir: Path, bc: str) -> dict[str, Path]:
    """Computes quadrant directory paths for a bounded context."""
    clean_bc = validate_bc_name(bc)
    docs = root_dir / "docs"
    return {
        "tutorials": docs / "tutorials" / clean_bc,
        "how-to": docs / "how-to" / clean_bc,
        "reference": docs / "reference" / clean_bc,
        "explanation": docs / "explanation" / clean_bc,
    }


def check_docs_exist(root_dir: Path, bc: str) -> bool:
    """Checks whether any documentation files already exist for the bounded context."""
    quadrants = get_quadrant_paths(root_dir, bc)
    for path in quadrants.values():
        if path.is_dir() and any(path.glob("*.md")):
            return True
    return False


def render_tutorial_doc(bc: str, title: str) -> str:
    deep_link = get_visualizer_deep_link(bc)
    return f"""---
title: "{title} Tutorials"
bounded_context: "{bc}"
quadrant: "tutorials"
status: "Draft"
governing_prd: "PRD-0005"
governing_story: "US-0071"
---

# {title} Tutorials

Welcome to the tutorials for the **{title}** bounded context (`{bc}`).

## Getting Started

This quadrant provides step-by-step learning guides for integrating and operating within the {title} subsystem.

👉 **[Explore {title} in Interactive 2D Visualizer]({deep_link})**

## Specifications & Requirements
- **Governing PRD**: [PRD Catalog](../../project/product/accepted/)
- **User Stories**: [User Stories Catalog](../../project/user_stories/PERSONAS.md)
"""


def render_howto_doc(bc: str, title: str) -> str:
    deep_link = get_visualizer_deep_link(bc)
    return f"""---
title: "{title} How-To Guides"
bounded_context: "{bc}"
quadrant: "how-to"
status: "Draft"
governing_prd: "PRD-0005"
governing_story: "US-0071"
---

# {title} How-To Guides

Practical, goal-oriented recipes for the **{title}** bounded context (`{bc}`).

## Operational Guides

Find operational recipes and workflows for configuring and maintaining {title}.

👉 **[Explore {title} in Interactive 2D Visualizer]({deep_link})**

## Specifications & Requirements
- **Governing PRD**: [PRD Catalog](../../project/product/accepted/)
- **User Stories**: [User Stories Catalog](../../project/user_stories/PERSONAS.md)
"""


def render_reference_doc(bc: str, title: str) -> str:
    deep_link = get_visualizer_deep_link(bc)
    return f"""---
title: "{title} Technical Reference"
bounded_context: "{bc}"
quadrant: "reference"
status: "Draft"
governing_prd: "PRD-0005"
governing_story: "US-0071"
---

# {title} Technical Reference

Authoritative technical and architectural reference for the **{title}** bounded context (`{bc}`).

## Architecture & Entities

Inspect the components, public interfaces, and domain models governing this bounded context.

👉 **[Explore {title} in Interactive 2D Visualizer]({deep_link})**

## Specifications & Traceability
- **Governing PRD**: [PRD Catalog](../../project/product/accepted/)
- **User Stories**: [User Stories Catalog](../../project/user_stories/PERSONAS.md)
"""


def render_explanation_index(bc: str, title: str) -> str:
    deep_link = get_visualizer_deep_link(bc)
    return f"""---
title: "{title} Domain Concepts & Boundaries"
bounded_context: "{bc}"
quadrant: "explanation"
status: "Draft"
governing_prd: "PRD-0005"
governing_story: "US-0071"
---

# {title} Domain Concepts & Boundaries

In-depth conceptual architecture and design rationale for the **{title}** bounded context (`{bc}`).

## Domain Model & Invariants

Understand the core domain boundaries, ubiquitous language, and DDD layering for {title}.

👉 **[Explore {title} in Interactive 2D Visualizer]({deep_link})**

## Specifications & Lineage
- **Governing PRD**: [PRD Catalog](../../project/product/accepted/)
- **User Stories**: [User Stories Catalog](../../project/user_stories/PERSONAS.md)
"""


def render_explanation_architecture(bc: str, title: str) -> str:
    deep_link = get_visualizer_deep_link(bc)
    return f"""---
title: "{title} Architecture & Domain Model"
bounded_context: "{bc}"
quadrant: "explanation"
status: "Draft"
governing_prd: "PRD-0005"
governing_story: "US-0071"
---

# {title} Architecture & Domain Model

Architectural overview and boundary invariants for the **{title}** bounded context (`{bc}`).

## Interactive 2D Visualizer
Explore this subsystem on the living project dependency canvas:

👉 **[Explore {title} in Interactive 2D Visualizer]({deep_link})**

## Domain Boundaries & Specifications
- **Governing Specifications**: [User Stories Catalog](../../project/user_stories/PERSONAS.md)
- **PRD Catalog**: [PRD Specifications](../../project/product/accepted/)
"""


def update_index_md(root_dir: Path, bc: str, title: str) -> Path | None:
    """Updates docs/index.md with a dedicated section for the bounded context."""
    index_path = root_dir / "docs" / "index.md"
    if not index_path.exists():
        return None
    content = index_path.read_text(encoding="utf-8")
    marker = f"### {title} (`{bc}`)"
    if marker in content:
        return index_path

    section = f"""### {title} (`{bc}`)
- [Tutorials](tutorials/{bc}/index.md)
- [How-To Guides](how-to/{bc}/index.md)
- [Reference](reference/{bc}/index.md)
- [Explanation](explanation/{bc}/index.md)
- 👉 **[Launch Visualizer for {title}](visualizer/?focus={bc}#tab=canvas&focus={bc})**
"""
    if "## Bounded Contexts" in content:
        updated = content.replace("## Bounded Contexts\n", f"## Bounded Contexts\n\n{section}\n")
    else:
        updated = content.rstrip() + f"\n\n---\n\n## Bounded Contexts\n\n{section}"

    index_path.write_text(updated.strip() + "\n", encoding="utf-8")
    return index_path


def scaffold_bc_docs(
    root_dir: Path,
    bc: str,
    title: str | None = None,
    force: bool = False,
) -> list[Path]:
    """Scaffolds Diataxis documentation quadrants for a bounded context."""
    clean_bc = validate_bc_name(bc)
    clean_title = normalize_title(clean_bc, title)

    if not force and check_docs_exist(root_dir, clean_bc):
        raise DocumentationExistsError(
            f"Diataxis documentation for bounded context '{clean_bc}' already exists. Use --force to overwrite."
        )

    quadrants = get_quadrant_paths(root_dir, clean_bc)
    for path in quadrants.values():
        path.mkdir(parents=True, exist_ok=True)

    created_files: list[Path] = []

    files_to_render = [
        (quadrants["tutorials"] / "index.md", render_tutorial_doc(clean_bc, clean_title)),
        (quadrants["how-to"] / "index.md", render_howto_doc(clean_bc, clean_title)),
        (quadrants["reference"] / "index.md", render_reference_doc(clean_bc, clean_title)),
        (quadrants["explanation"] / "index.md", render_explanation_index(clean_bc, clean_title)),
        (quadrants["explanation"] / "architecture.md", render_explanation_architecture(clean_bc, clean_title)),
    ]

    for file_path, doc_content in files_to_render:
        file_path.write_text(doc_content.strip() + "\n", encoding="utf-8")
        created_files.append(file_path)

    idx_path = update_index_md(root_dir, clean_bc, clean_title)
    if idx_path is not None:
        created_files.append(idx_path)

    return created_files
