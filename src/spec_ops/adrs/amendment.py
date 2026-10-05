"""Living Architectural Decision Record (ADR) Amendment Engine."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
import re
from typing import Any
import yaml

from ..core.parser import extract_frontmatter
from .amend import (
    AmendResult,
    CircularAmendmentError,
    detect_amendment_cycles,
    discover_amended_adrs,
    update_registry_amendment,
)
from .supersede import (
    ADRNotFoundError,
    find_adr_file,
    normalize_adr_id,
    parse_adr_info,
    write_adr_frontmatter,
)
from .supersession import find_next_adr_id, slugify


class ADRAmendmentEngine:
    """Coordinates living ADR amendments, replacement scaffolding, and registry synchronization."""

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
        p = self.root_dir / "docs" / "project" / "adrs"
        p.mkdir(parents=True, exist_ok=True)
        return p

    def scaffold_amending_adr(
        self,
        new_id: str,
        title: str,
        old_id: str,
        adrs_dir: Path,
        dry_run: bool = False,
    ) -> Path:
        """Scaffolds a new amending ADR file with decision context and consequences."""
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
            "amends": [old_id],
        }

        body = f"""# {new_id}: {title}

## Status
Accepted (amends [`{old_id}`](file://{old_id.lower()}.md))

## Context
This decision incrementally amends `{old_id}` to refine architectural standards and operational requirements.

## Decision
We amend `{old_id}` with `{new_id}` ({title}).

## Consequences
- The foundational decision `{old_id}` remains active and authoritative.
- Incremental refinements and updated specifications are codified in `{new_id}`.
"""
        if not dry_run:
            yaml_str = yaml.dump(meta, sort_keys=False, default_flow_style=False).strip()
            new_path.write_text(f"---\n{yaml_str}\n---\n\n{body}\n", encoding="utf-8")

        return new_path

    def amend(
        self,
        old_target: str | Path,
        new_target: str | Path | None = None,
        title: str | None = None,
        dry_run: bool = False,
    ) -> AmendResult:
        """Executes ADR amendment, linking old and new ADRs without retiring the predecessor."""
        adrs_dir = self.get_adrs_dir()

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
            new_meta = {}
            new_body = ""
        else:
            raise ValueError("Must provide either amending target ADR identifier or a new title.")

        # Check for circular amendment BEFORE modifying any files
        existing_map = discover_amended_adrs(adrs_dir)
        detect_amendment_cycles(existing_map, (new_id, old_id))

        if not dry_run:
            if not new_target and title:
                new_file = self.scaffold_amending_adr(
                    new_id=new_id,
                    title=title,
                    old_id=old_id,
                    adrs_dir=adrs_dir,
                    dry_run=False,
                )
            else:
                new_meta["status"] = "Accepted"
                raw_amends = new_meta.get("amends", [])
                if isinstance(raw_amends, list):
                    amends_list = [normalize_adr_id(str(x)) for x in raw_amends]
                elif raw_amends:
                    amends_list = [normalize_adr_id(str(raw_amends))]
                else:
                    amends_list = []
                if old_id not in amends_list:
                    amends_list.append(old_id)
                new_meta["amends"] = amends_list

                accepted_dir = adrs_dir / "accepted"
                accepted_dir.mkdir(parents=True, exist_ok=True)
                if new_file.parent.resolve() != accepted_dir.resolve():
                    dest = accepted_dir / new_file.name
                    new_file.rename(dest)
                    new_file = dest
                write_adr_frontmatter(new_file, new_meta, new_body)

            # Update old ADR frontmatter: append new_id to amended_by and preserve status Accepted
            old_meta["status"] = old_meta.get("status") or "Accepted"
            raw_amended_by = old_meta.get("amended_by", [])
            if isinstance(raw_amended_by, list):
                amended_by_list = [normalize_adr_id(str(x)) for x in raw_amended_by]
            elif raw_amended_by:
                amended_by_list = [normalize_adr_id(str(raw_amended_by))]
            else:
                amended_by_list = []
            if new_id not in amended_by_list:
                amended_by_list.append(new_id)
            old_meta["amended_by"] = amended_by_list

            write_adr_frontmatter(old_file, old_meta, old_body)

            # Synchronize REGISTRY.md without marking old_id as Superseded
            registry_file = adrs_dir / "REGISTRY.md"
            update_registry_amendment(registry_file, old_id, new_id, new_title)

        return AmendResult(
            old_id=old_id,
            new_id=new_id,
            old_file=old_file,
            new_file=new_file,
            warnings=[],
        )
