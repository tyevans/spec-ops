"""PRD vertical slice and spike decomposition engine."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.parser import extract_frontmatter
from .delta import (
    CheckableOutcome,
    FalsifiabilityError,
    PRDDeltaResult,
    calculate_prd_deltas,
    find_existing_stories,
    find_existing_tasks,
    parse_checkable_outcomes,
    validate_falsifiability,
)
from .synthesis import (
    append_to_priority,
    generate_outcome_stories_and_tasks,
    update_prd_links,
)


class PRDDecomposer:
    """Decomposes PRDs into granular vertical slices and user stories."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config
        self.prd_dir = config.prd_dir
        self.backlog_dir = config.backlog_dir
        self.stories_dir = config.user_stories_dir

    def get_max_task_number(self) -> int:
        max_id = 0
        if self.backlog_dir.exists():
            for p in self.backlog_dir.rglob("*.md"):
                m = re.match(r"^(\d+)", p.stem)
                if m:
                    max_id = max(max_id, int(m.group(1)))
        return max_id

    def get_max_story_number(self) -> int:
        max_id = 0
        if self.stories_dir.exists():
            for p in self.stories_dir.rglob("*.md"):
                m = re.search(r"us-(\d+)", p.name, re.IGNORECASE)
                if m:
                    max_id = max(max_id, int(m.group(1)))
        return max_id

    def find_prd_file(self, prd_identifier: str) -> Path | None:
        clean = prd_identifier.replace("PRD-", "").lstrip("0")
        target_pat = re.compile(rf"prd-0*{clean}-", re.IGNORECASE)
        for p in self.prd_dir.rglob("*.md"):
            if target_pat.search(p.name):
                return p
        return None

    def decompose(
        self,
        prd_identifier: str,
        include_spike: bool = True,
        slices_override: list[str] | None = None,
    ) -> list[Path]:
        """Decomposes a PRD into tasks and user stories (legacy single-pass)."""
        prd_file = self.find_prd_file(prd_identifier)
        if not prd_file or not prd_file.exists():
            raise FileNotFoundError(f"PRD not found matching identifier: {prd_identifier}")

        prd_content = prd_file.read_text(encoding="utf-8")
        meta, _ = extract_frontmatter(prd_content)
        prd_title = str(meta.get("title", prd_file.stem))
        persona = str(meta.get("target_persona", "User"))
        component = str(meta.get("component", "core"))

        clean_prd_num = str(meta.get("id", "0001")).zfill(4)
        prd_canonical_id = f"PRD-{clean_prd_num}"

        task_num = self.get_max_task_number()
        story_num = self.get_max_story_number()

        today = date.today().isoformat()
        proposed_dir = self.backlog_dir / "proposed"
        proposed_dir.mkdir(parents=True, exist_ok=True)
        accepted_stories_dir = self.stories_dir / "accepted"
        accepted_stories_dir.mkdir(parents=True, exist_ok=True)

        generated_task_files: list[Path] = []
        created_task_ids: list[str] = []
        created_story_ids: list[str] = []

        # 1. Generate User Story
        story_num += 1
        story_cid = f"US-{story_num:04d}"
        story_slug = "".join(c if c.isalnum() else "-" for c in prd_title.lower()).strip("-")[:40]
        story_file = accepted_stories_dir / f"us-{story_num:04d}-{story_slug}.md"

        story_content = f"""---
id: '{story_num:04d}'
title: {prd_title}
status: Accepted
created: {today}
persona: {persona}
governing_prd: {prd_canonical_id}
---

# {story_cid} — {prd_title}

## Governing PRD
- [`{prd_canonical_id}`](../../product/accepted/{prd_file.name})

## User Story

**As a** {persona or "developer"},  
**I want** to interact with {prd_title.lower()},  
**So that** I achieve the desired outcome reliably.

## Acceptance Criteria

### Scenario 1: Successful Primary Journey
```gherkin
Given the system is initialized and ready
When the user executes the primary workflow for "{prd_title}"
Then observable outputs reflect the updated state
And no internal invariants are violated.
```
"""
        story_file.write_text(story_content, encoding="utf-8")
        created_story_ids.append(story_cid)

        # 2. Generate Slices from Config
        active_slices = self.config.vertical_slices
        spike_id = None

        for s_cfg in active_slices:
            if s_cfg.type == "spike" and not include_spike:
                continue

            task_num += 1
            tid = f"TASK-{task_num:04d}"
            t_title = f"{s_cfg.prefix} {s_cfg.name} for {prd_title}".strip()
            t_slug = "".join(c if c.isalnum() else "-" for c in t_title.lower()).strip("-")[:40]
            task_file = proposed_dir / f"{task_num:04d}-{t_slug}.md"

            deps = [spike_id] if (spike_id and s_cfg.type != "spike") else []

            task_content = f"""---
id: '{task_num:04d}'
title: "{t_title.replace('"', '\\"')}"
status: Proposed
created: {today}
dependencies: {deps}
governing_prds:
  - {prd_canonical_id}
governing_stories:
  - {story_cid}
target_bc: {component}
---

# {tid}: {t_title}

## Summary
Implement {s_cfg.name.lower()} in component `{component}` fulfilling {prd_canonical_id}.

## Problem Statement
Deliver focused slice satisfying INVEST criteria and Hard Invariant 6 (<500 lines).

## Definition of Done (Blackbox Frontdoor TDD)
1. Public interfaces or standard domain contracts implemented.
2. Verified via automated blackbox tests with zero private backdoor manipulation.
3. All new source files strictly under 500 lines.
"""
            task_file.write_text(task_content, encoding="utf-8")
            generated_task_files.append(task_file)
            created_task_ids.append(tid)

            if s_cfg.type == "spike":
                spike_id = tid

        # 3. Update PRD with linked user stories and implementing tasks
        update_prd_links(prd_file, created_story_ids, created_task_ids)

        # 4. Append tasks to PRIORITY.md
        append_to_priority(self.backlog_dir, created_task_ids, generated_task_files)

        return generated_task_files

    def decompose_by_outcomes(
        self,
        prd_identifier: str,
        include_spike: bool = True,
    ) -> tuple[list[Path], list[Path]]:
        """Decomposes each checkable outcome in a PRD into dedicated BDD user stories and tasks."""
        prd_file = self.find_prd_file(prd_identifier)
        if not prd_file or not prd_file.exists():
            raise FileNotFoundError(f"PRD not found matching identifier: {prd_identifier}")

        prd_content = prd_file.read_text(encoding="utf-8")
        meta, _ = extract_frontmatter(prd_content)
        prd_title = str(meta.get("title", prd_file.stem))
        persona = str(meta.get("target_persona", "User"))
        component = str(meta.get("component", "core"))

        clean_prd_num = str(meta.get("id", "0001")).zfill(4)
        prd_canonical_id = f"PRD-{clean_prd_num}"

        outcomes = parse_checkable_outcomes(prd_content)
        if not outcomes:
            raise ValueError(f"No checkable outcomes found in {prd_canonical_id}")

        errors = validate_falsifiability(outcomes)
        if errors:
            raise FalsifiabilityError(errors)

        return self._generate_outcome_stories_and_tasks(
            prd_file=prd_file,
            prd_canonical_id=prd_canonical_id,
            prd_title=prd_title,
            persona=persona,
            component=component,
            outcomes=outcomes,
            include_spike=include_spike,
        )

    def decompose_diff(
        self,
        prd_identifier: str,
        include_spike: bool = True,
    ) -> tuple[PRDDeltaResult, list[Path], list[Path]]:
        """Performs non-destructive delta scope evolution for newly added or modified outcomes."""
        prd_file = self.find_prd_file(prd_identifier)
        if not prd_file or not prd_file.exists():
            raise FileNotFoundError(f"PRD not found matching identifier: {prd_identifier}")

        prd_content = prd_file.read_text(encoding="utf-8")
        meta, _ = extract_frontmatter(prd_content)
        prd_title = str(meta.get("title", prd_file.stem))
        persona = str(meta.get("target_persona", "User"))
        component = str(meta.get("component", "core"))

        clean_prd_num = str(meta.get("id", "0001")).zfill(4)
        prd_canonical_id = f"PRD-{clean_prd_num}"

        current_outcomes = parse_checkable_outcomes(prd_content)
        existing_stories = find_existing_stories(self.stories_dir, prd_canonical_id)
        stories_map = {
            s["id"].upper().replace("US-", "").lstrip("0"): s["outcome_id"]
            for s in existing_stories
            if s.get("outcome_id") is not None
        }
        existing_tasks = find_existing_tasks(self.backlog_dir, prd_canonical_id, stories_map)

        delta_res = calculate_prd_deltas(
            prd_id=prd_canonical_id,
            current_outcomes=current_outcomes,
            existing_stories=existing_stories,
            existing_tasks=existing_tasks,
        )

        if not delta_res.added_outcomes:
            return delta_res, [], []

        errors = validate_falsifiability(delta_res.added_outcomes)
        if errors:
            raise FalsifiabilityError(errors)

        # Skip spike for delta runs if tasks already exist for this PRD
        has_existing_tasks = len(existing_tasks) > 0
        diff_include_spike = include_spike and not has_existing_tasks

        task_files, story_files = self._generate_outcome_stories_and_tasks(
            prd_file=prd_file,
            prd_canonical_id=prd_canonical_id,
            prd_title=prd_title,
            persona=persona,
            component=component,
            outcomes=delta_res.added_outcomes,
            include_spike=diff_include_spike,
        )

        return delta_res, task_files, story_files

    def _generate_outcome_stories_and_tasks(
        self,
        prd_file: Path,
        prd_canonical_id: str,
        prd_title: str,
        persona: str,
        component: str,
        outcomes: list[CheckableOutcome],
        include_spike: bool,
    ) -> tuple[list[Path], list[Path]]:
        return generate_outcome_stories_and_tasks(
            prd_file=prd_file,
            prd_canonical_id=prd_canonical_id,
            prd_title=prd_title,
            persona=persona,
            component=component,
            outcomes=outcomes,
            include_spike=include_spike,
            config=self.config,
            backlog_dir=self.backlog_dir,
            stories_dir=self.stories_dir,
            task_num_start=self.get_max_task_number(),
            story_num_start=self.get_max_story_number(),
        )
