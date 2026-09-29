"""PRD vertical slice and spike decomposition engine."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.parser import SpecOpsParser, extract_frontmatter


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
        """Decomposes a PRD into tasks and user stories."""
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
title: {t_title}
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
        self._update_prd_links(prd_file, created_story_ids, created_task_ids)

        # 4. Append tasks to PRIORITY.md
        self._append_to_priority(created_task_ids, generated_task_files)

        return generated_task_files

    def _update_prd_links(self, prd_file: Path, story_ids: list[str], task_ids: list[str]) -> None:
        content = prd_file.read_text(encoding="utf-8")
        stories_section = "\n".join(f"- `{sid}`" for sid in story_ids)
        tasks_section = "\n".join(f"- `{tid}`" for tid in task_ids)

        if "## Linked User Stories" in content:
            content = re.sub(
                r"## Linked User Stories\s*\n.*?(?=\n##|$)",
                f"## Linked User Stories\n\n{stories_section}\n",
                content,
                flags=re.DOTALL,
            )
        else:
            content += f"\n## Linked User Stories\n\n{stories_section}\n"

        if "## Implementing Backlog Tasks" in content:
            content = re.sub(
                r"## Implementing Backlog Tasks\s*\n.*?(?=\n##|$)",
                f"## Implementing Backlog Tasks\n\n{tasks_section}\n",
                content,
                flags=re.DOTALL,
            )
        else:
            content += f"\n## Implementing Backlog Tasks\n\n{tasks_section}\n"

        prd_file.write_text(content, encoding="utf-8")

    def _append_to_priority(self, task_ids: list[str], task_files: list[Path]) -> None:
        priority_file = self.backlog_dir / "PRIORITY.md"
        if not priority_file.exists():
            return
        lines = priority_file.read_text(encoding="utf-8").splitlines()
        for tid, tf in zip(task_ids, task_files):
            entry = f"- **{tid} (Proposed)**: [`{tf.stem}`](proposed/{tf.name})"
            if entry not in lines:
                lines.append(entry)
        priority_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
