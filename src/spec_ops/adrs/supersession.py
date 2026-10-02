"""Living Architectural Decision Record (ADR) Supersession and Evolution Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
import re
from typing import Any
import yaml

from ..core.parser import extract_frontmatter
from .supersede import (
    ADRNotFoundError,
    CircularSupersessionError,
    SupersedeResult,
    detect_supersession_cycles,
    discover_superseded_adrs,
    find_adr_file,
    find_tasks_citing_adr,
    normalize_adr_id,
    parse_adr_info,
    update_registry_supersession,
    write_adr_frontmatter,
)


def slugify(text: str) -> str:
    """Converts a human title into a lowercase alphanumeric hyphenated slug."""
    clean = re.sub(r"[^\w\s-]", "", text.lower())
    clean = re.sub(r"[\s_-]+", "-", clean)
    return clean.strip("-")


def find_next_adr_id(adrs_dir: Path) -> tuple[str, int]:
    """Finds the next sequential ADR identifier by inspecting docs/project/adrs/."""
    max_num = 0
    if adrs_dir.exists():
        for p in adrs_dir.rglob("*.md"):
            m = re.search(r"adr-(\d+)", p.stem, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                if val > max_num:
                    max_num = val
    next_num = max_num + 1
    return f"ADR-{next_num:04d}", next_num


class ADRSupersessionEngine:
    """Coordinates living ADR supersession, automated replacement scaffolding, and registry synchronization."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir or Path.cwd()

    def get_adrs_dir(self) -> Path:
        """Locates the project ADR directory."""
        candidates = [
            self.root_dir / "docs" / "project" / "adrs",
            self.root_dir / "docs" / "adrs",
            self.root_dir / "adrs",
        ]
        for c in candidates:
            if c.exists():
                return c
        # Default scaffold path
        p = self.root_dir / "docs" / "project" / "adrs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def scaffold_superseding_adr(
        self,
        new_id: str,
        title: str,
        old_id: str,
        adrs_dir: Path,
        dry_run: bool = False,
    ) -> Path:
        """Scaffolds a new replacement ADR file with initial decision context and consequences."""
        slug = slugify(title)
        num_match = re.search(r"\d+", new_id)
        num_str = f"{int(num_match.group(0)):04d}" if num_match else "0001"
        filename = f"adr-{num_str}-{slug}.md" if slug else f"adr-{num_str}.md"

        accepted_dir = adrs_dir / "accepted"
        accepted_dir.mkdir(parents=True, exist_ok=True)
        new_path = accepted_dir / filename

        meta = {
            "id": new_id,
            "title": title,
            "status": "Accepted",
            "date": date.today().isoformat(),
            "supersedes": old_id,
        }

        body = f"""# {new_id}: {title}

## Status
Accepted (supersedes [`{old_id}`](file://{old_id.lower()}.md))

## Context
This decision supersedes `{old_id}` to evolve the architectural standards and operational requirements.

## Decision
We supersede `{old_id}` with `{new_id}` ({title}).

## Consequences
- The legacy decision `{old_id}` is retired and marked as Superseded.
- Downstream tasks and workflows cite `{new_id}` for architectural governance.
"""
        if not dry_run:
            yaml_str = yaml.dump(meta, sort_keys=False, default_flow_style=False).strip()
            new_path.write_text(f"---\n{yaml_str}\n---\n\n{body}\n", encoding="utf-8")

        return new_path

    def supersede(
        self,
        old_target: str | Path,
        new_target: str | Path | None = None,
        title: str | None = None,
        dry_run: bool = False,
    ) -> SupersedeResult:
        """Executes ADR supersession, creating a new ADR if title is provided, and updating old ADR."""
        adrs_dir = self.get_adrs_dir()
        backlog_dir = self.root_dir / "docs" / "project" / "backlog"

        old_file = find_adr_file(adrs_dir, old_target)
        old_meta, old_body, old_title, old_id = parse_adr_info(old_file)

        # Determine new ADR ID and file
        if new_target:
            new_file = find_adr_file(adrs_dir, new_target)
            new_meta, new_body, new_title, new_id = parse_adr_info(new_file)
        elif title:
            new_id, _ = find_next_adr_id(adrs_dir)
            new_title = title
            slug = slugify(title)
            num_match = re.search(r"\d+", new_id)
            num_str = f"{int(num_match.group(0)):04d}" if num_match else "0001"
            filename = f"adr-{num_str}-{slug}.md" if slug else f"adr-{num_str}.md"
            new_file = (adrs_dir / "accepted" / filename).resolve()
        else:
            raise ValueError("Must provide either superseding target ADR identifier or a new title.")

        # Check for circular supersession before touching files
        existing_map = discover_superseded_adrs(adrs_dir)
        detect_supersession_cycles(existing_map, (old_id, new_id))

        if not dry_run:
            if not new_target and title:
                new_file = self.scaffold_superseding_adr(
                    new_id=new_id,
                    title=title,
                    old_id=old_id,
                    adrs_dir=adrs_dir,
                    dry_run=False,
                )
            else:
                new_meta["status"] = "Accepted"
                new_meta["supersedes"] = old_id
                if "## Status" in new_body:
                    new_body = re.sub(r"## Status\s*\n[^\n]+", "## Status\nAccepted", new_body)

                accepted_dir = adrs_dir / "accepted"
                accepted_dir.mkdir(parents=True, exist_ok=True)
                if new_file.parent.resolve() != accepted_dir.resolve():
                    dest = accepted_dir / new_file.name
                    new_file.rename(dest)
                    new_file = dest
                write_adr_frontmatter(new_file, new_meta, new_body)

            # Update old ADR
            old_meta["status"] = "Superseded"
            old_meta["superseded_by"] = new_id
            if "## Status" in old_body:
                old_body = re.sub(
                    r"## Status\s*\n[^\n]+",
                    f"## Status\nSuperseded (by {new_id})",
                    old_body,
                )
            else:
                old_body = f"## Status\nSuperseded (by {new_id})\n\n{old_body}"
            write_adr_frontmatter(old_file, old_meta, old_body)

            # Update REGISTRY.md
            registry_file = adrs_dir / "REGISTRY.md"
            update_registry_supersession(registry_file, old_id, new_id, new_title)

        citing_tasks = find_tasks_citing_adr(backlog_dir, old_id)
        warnings = [
            f"Task {tid} cites superseded {old_id}; requires architectural re-refinement"
            for tid in citing_tasks
        ]

        return SupersedeResult(
            old_id=old_id,
            new_id=new_id,
            old_file=old_file,
            new_file=new_file,
            warnings=warnings,
        )
