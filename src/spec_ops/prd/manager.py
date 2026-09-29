"""PRD management, health auditing, and creation workflow."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.parser import SpecOpsParser, extract_frontmatter


@dataclass
class PRDAuditResult:
    total_prds: int = 0
    undecomposed_prds: list[str] = field(default_factory=list)
    ready_tasks_count: int = 0
    buffer_status: str = "OPTIMAL"
    warnings: list[str] = field(default_factory=list)


class PRDManager:
    """Manages PRD lifecycle stages and health auditing."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config
        self.prd_dir = config.prd_dir
        self.backlog_dir = config.backlog_dir

    def get_next_prd_id(self) -> str:
        """Calculates next PRD ID sequentially."""
        max_id = 0
        if self.prd_dir.exists():
            for p in self.prd_dir.rglob("*.md"):
                m = re.search(r"prd-(\d+)", p.name, re.IGNORECASE)
                if m:
                    max_id = max(max_id, int(m.group(1)))
        return f"PRD-{(max_id + 1):04d}"

    def create_prd(
        self,
        title: str,
        persona: str = "",
        component: str = "",
        summary: str = "",
        stage: str = "accepted",
    ) -> Path:
        """Scaffolds a new PRD document in the target stage directory."""
        prd_id = self.get_next_prd_id()
        slug = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")
        clean_num = prd_id.split("-")[-1]
        filename = f"prd-{clean_num}-{slug[:45]}.md"

        target_dir = self.prd_dir / stage
        target_dir.mkdir(parents=True, exist_ok=True)
        file_path = target_dir / filename

        today = date.today().isoformat()
        content = f"""---
id: '{clean_num}'
title: {title}
status: {stage.capitalize()}
created: {today}
target_persona: {persona}
component: {component}
---

# {prd_id} — {title}

## Who this is for

- **{persona or "Target User"}**: {summary or "Problem statement and user context."}

## What the person cannot do today

- Document existing friction, manual workarounds, or missing platform capabilities.

## What good looks like

1. **Core Capability**:
   - High-level capability description.

## What this does not do

- Explicit scope boundaries and non-goals.

## Checkable Outcomes

1. Observable and falsifiable verification criteria via public interfaces.

## Linked User Stories

<!-- Added during decomposition -->

## Implementing Backlog Tasks

<!-- Added during decomposition -->
"""
        file_path.write_text(content, encoding="utf-8")
        return file_path

    def audit(self) -> PRDAuditResult:
        """Audits PRD decomposition state and buffer readiness."""
        parser = SpecOpsParser(self.config.project_docs_dir)
        data = parser.parse_all()

        ready_count = sum(1 for t in data.tasks if t.status == "Refined")
        undecomposed: list[str] = []
        warnings: list[str] = []

        for prd in data.prds:
            if not prd.implementing_tasks:
                undecomposed.append(prd.id)

        target_buffer = self.config.architecture.buffer_target
        threshold = self.config.architecture.buffer_warning_threshold
        buffer_status = "OPTIMAL"

        if ready_count < threshold:
            buffer_status = "UNDER_BUFFERED"
            warnings.append(
                f"Ready buffer is low ({ready_count} < {threshold}). Decompose PRDs or run curation."
            )
        elif ready_count > target_buffer * 2:
            buffer_status = "OVER_BUFFERED"

        return PRDAuditResult(
            total_prds=len(data.prds),
            undecomposed_prds=undecomposed,
            ready_tasks_count=ready_count,
            buffer_status=buffer_status,
            warnings=warnings,
        )
