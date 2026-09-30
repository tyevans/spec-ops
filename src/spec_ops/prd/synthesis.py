"""PRD outcome and slice synthesis, user story formatting, and backlog link updating."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from ..config.models import SpecOpsConfig
from .delta import CheckableOutcome


def update_prd_links(prd_file: Path, story_ids: list[str], task_ids: list[str]) -> None:
    """Updates or appends linked user stories and implementing tasks in the PRD file."""
    content = prd_file.read_text(encoding="utf-8")

    # Extract and merge existing linked user stories
    existing_stories: list[str] = []
    m_s = re.search(r"## Linked User Stories\s*\n(.*?)(?=\n##|$)", content, re.DOTALL)
    if m_s:
        existing_stories = re.findall(r"- `?([A-Za-z0-9_\-]+)`?", m_s.group(1))

    all_stories: list[str] = []
    for s in [*existing_stories, *story_ids]:
        if s not in all_stories:
            all_stories.append(s)

    stories_section = "\n".join(f"- `{sid}`" for sid in all_stories)

    # Extract and merge existing implementing backlog tasks
    existing_tasks: list[str] = []
    m_t = re.search(r"## Implementing Backlog Tasks\s*\n(.*?)(?=\n##|$)", content, re.DOTALL)
    if m_t:
        existing_tasks = re.findall(r"- `?([A-Za-z0-9_\-]+)`?", m_t.group(1))

    all_tasks: list[str] = []
    for t in [*existing_tasks, *task_ids]:
        if t not in all_tasks:
            all_tasks.append(t)

    tasks_section = "\n".join(f"- `{tid}`" for tid in all_tasks)

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


def append_to_priority(backlog_dir: Path, task_ids: list[str], task_files: list[Path]) -> None:
    """Appends newly generated tasks to PRIORITY.md if not already present."""
    priority_file = backlog_dir / "PRIORITY.md"
    if not priority_file.exists():
        return
    lines = priority_file.read_text(encoding="utf-8").splitlines()
    for tid, tf in zip(task_ids, task_files):
        entry = f"- **{tid} (Proposed)**: [`{tf.stem}`](proposed/{tf.name})"
        if entry not in lines:
            lines.append(entry)
    priority_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def generate_outcome_stories_and_tasks(
    prd_file: Path,
    prd_canonical_id: str,
    prd_title: str,
    persona: str,
    component: str,
    outcomes: list[CheckableOutcome],
    include_spike: bool,
    config: SpecOpsConfig,
    backlog_dir: Path,
    stories_dir: Path,
    task_num_start: int,
    story_num_start: int,
) -> tuple[list[Path], list[Path]]:
    """Generates BDD story files and vertical slice tasks for discrete checkable outcomes."""
    task_num = task_num_start
    story_num = story_num_start
    today = date.today().isoformat()

    proposed_dir = backlog_dir / "proposed"
    proposed_dir.mkdir(parents=True, exist_ok=True)
    accepted_stories_dir = stories_dir / "accepted"
    accepted_stories_dir.mkdir(parents=True, exist_ok=True)

    generated_task_files: list[Path] = []
    generated_story_files: list[Path] = []
    created_task_ids: list[str] = []
    created_story_ids: list[str] = []

    active_slices = config.vertical_slices
    spike_id = None
    spike_created = False

    for outcome in outcomes:
        story_num += 1
        story_cid = f"US-{story_num:04d}"
        story_slug = "".join(
            c if c.isalnum() else "-" for c in outcome.clean_text.lower()
        ).strip("-")[:40]
        story_file = accepted_stories_dir / f"us-{story_num:04d}-{story_slug}.md"

        story_content = f"""---
id: '{story_num:04d}'
title: "{outcome.clean_text.replace('"', '\\"')}"
status: Accepted
created: {today}
persona: {persona}
governing_prd: {prd_canonical_id}
outcome_id: {outcome.id}
---

# {story_cid} — {outcome.clean_text}

## Governing PRD
- [`{prd_canonical_id}`](../../product/accepted/{prd_file.name})

## User Story

**As a** {persona or "developer"},  
**I want** {outcome.clean_text},  
**So that** observable contracts and business requirements are fulfilled.

## Acceptance Criteria

```gherkin
Scenario: Verify {outcome.clean_text}
Given the system is initialized and ready
When the user executes the workflow for "{outcome.clean_text}"
Then observable outputs reflect the expected state: "{outcome.clean_text}"
And no internal invariants are violated.
```
"""
        story_file.write_text(story_content, encoding="utf-8")
        generated_story_files.append(story_file)
        created_story_ids.append(story_cid)

        for s_cfg in active_slices:
            if s_cfg.type == "spike":
                if not include_spike or spike_created:
                    continue
                spike_created = True

            task_num += 1
            tid = f"TASK-{task_num:04d}"
            t_title = f"{s_cfg.prefix} {s_cfg.name} for {outcome.clean_text}".strip()
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
outcome_id: {outcome.id}
target_bc: {component}
---

# {tid}: {t_title}

## Summary
Implement {s_cfg.name.lower()} in component `{component}` fulfilling Outcome {outcome.id} of {prd_canonical_id}.

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

    update_prd_links(prd_file, created_story_ids, created_task_ids)
    append_to_priority(backlog_dir, created_task_ids, generated_task_files)

    return generated_task_files, generated_story_files
