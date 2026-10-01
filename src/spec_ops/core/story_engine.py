"""Multi-faceted BDD user story generation and cross-cutting traceability engine.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0007, ADR-0008; PRD-0006; US-0117.
Target Bounded Context: core. File length strictly under 400 lines.
"""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
import re
from typing import Any
import yaml

from ..config.loader import load_config
from ..config.models import SpecOpsConfig
from ..core.git_metadata import GitMetadataHarvester
from ..core.models import ProjectData, Task, UserStory
from ..core.parser import SpecOpsParser, extract_frontmatter
from .story_models import (
    StoryScaffoldResult,
    StoryTraceItem,
    StoryTraceReport,
    normalize_story_id,
    slugify_story_title,
)


class StoryEngine:
    """Autonomous multi-faceted user story authoring and cross-cutting traceability engine."""

    def __init__(self, root_dir: str | Path | None = None, config: SpecOpsConfig | None = None):
        if config is not None:
            self.config = config
        else:
            self.config = load_config(root_dir)
        self.root_dir = self.config.root_dir
        self.project_docs = self.config.project_docs_dir
        self.stories_dir = self.project_docs / "user_stories" / "accepted"
        self.registry_path = self.project_docs / "user_stories" / "REGISTRY.md"
        self.personas_path = self.project_docs / "user_stories" / "PERSONAS.md"
        self.product_dir = self.project_docs / "product"

    def get_next_story_number(self) -> int:
        """Finds the next sequential integer story number across stories and REGISTRY.md."""
        max_num = 0
        if self.stories_dir.exists():
            for p in self.project_docs.rglob("*.md"):
                if "user_stories" in p.parts:
                    m = re.search(r"(?:us-)?(\d+)", p.stem, re.IGNORECASE)
                    if m:
                        max_num = max(max_num, int(m.group(1)))

        if self.registry_path.is_file():
            content = self.registry_path.read_text(encoding="utf-8", errors="ignore")
            for m in re.finditer(r"US-(\d+)", content):
                max_num = max(max_num, int(m.group(1)))

        return max_num + 1

    def create_story(
        self,
        title: str,
        prd: str,
        persona: str,
        bc: str = "core",
        story_id: str | None = None,
        feature: str | None = None,
        scenarios: list[str] | None = None,
        dry_run: bool = False,
    ) -> StoryScaffoldResult:
        """Scaffolds a new multi-faceted BDD user story and atomically updates REGISTRY.md."""
        if story_id:
            m = re.search(r"\d+", story_id)
            num = int(m.group(0)) if m else self.get_next_story_number()
        else:
            num = self.get_next_story_number()

        cid = f"US-{num:04d}"
        slug = slugify_story_title(title)
        filename = f"us-{num:04d}-{slug}.md"
        target_path = self.stories_dir / filename

        prd_cid = normalize_story_id(prd, "PRD") if prd else "PRD-0001"
        feature_code = feature or f"FEAT-{slugify_story_title(bc).upper()[:4]}-{num % 100:02d}"

        # Resolve PRD details if present
        prd_title = prd_cid
        prd_link = f"../../product/accepted/{prd_cid.lower()}.md"
        if self.product_dir.exists():
            for prd_file in self.product_dir.rglob("*.md"):
                if prd_cid.lower() in prd_file.stem.lower():
                    prd_meta, _ = extract_frontmatter(prd_file.read_text(encoding="utf-8", errors="ignore"))
                    prd_title = str(prd_meta.get("title", prd_cid))
                    prd_link = f"../../product/accepted/{prd_file.name}"
                    break

        scenario_list = scenarios or [f"Multi-Faceted BDD Story Generation for {title}"]

        # Build YAML frontmatter
        fm_lines = [
            f"id: '{num:04d}'",
            f"title: {json.dumps(title, ensure_ascii=False)}",
            "status: Accepted",
            f"created: {date.today().isoformat()}",
            f"persona: {json.dumps(persona, ensure_ascii=False)}",
            f"target_bc: {json.dumps(bc, ensure_ascii=False)}",
            f"feature: {json.dumps(feature_code, ensure_ascii=False)}",
            f"governing_prd: {json.dumps(prd_cid, ensure_ascii=False)}",
            "scenarios:",
        ]
        for sc in scenario_list:
            fm_lines.append(f"  - {json.dumps(sc, ensure_ascii=False)}")
        fm_text = "\n".join(fm_lines)

        # Build Gherkin acceptance criteria
        gherkin_blocks: list[str] = []
        for sc in scenario_list:
            gherkin_blocks.append(
                f"```gherkin\n"
                f"Scenario: {sc}\n"
                f"  Given the system is initialized and ready\n"
                f'  When the user executes the workflow for "{sc}"\n'
                f"  Then observable outputs satisfy public contracts without backdoor tampering.\n"
                f"```"
            )
        gherkin_text = "\n\n".join(gherkin_blocks)

        persona_role = persona
        content = (
            f"---\n{fm_text}\n---\n\n"
            f"# {cid} — {title}\n\n"
            f"## Governing PRD\n"
            f"- [`{prd_cid}: {prd_title}`]({prd_link})\n\n"
            f"## User Story\n\n"
            f"**As an** {persona_role},\n"
            f'**I want** an autonomous capability to execute "{title}",\n'
            f"**So that** business outcomes are delivered reliably across the {bc} bounded context.\n\n"
            f"## Acceptance Criteria\n\n"
            f"{gherkin_text}\n"
        )

        reg_updated = False
        if not dry_run:
            self.stories_dir.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
            self.update_registry(
                cid=cid,
                title=title,
                status="Accepted",
                persona=persona,
                feature=feature_code,
                governing_prd=prd_cid,
            )
            reg_updated = True

        return StoryScaffoldResult(
            id=cid,
            title=title,
            file_path=target_path,
            content=content,
            registry_updated=reg_updated,
            dry_run=dry_run,
        )

    def update_registry(
        self,
        cid: str,
        title: str,
        status: str,
        persona: str,
        feature: str,
        governing_prd: str,
    ) -> None:
        """Atomically updates docs/project/user_stories/REGISTRY.md with the story record."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        rows: dict[int, str] = {}
        header_lines = [
            "# User Stories Registry",
            "",
            "| ID | Title | Status | Persona | Feature | Governing PRD |",
            "|---|---|---|---|---|---|",
        ]

        if self.registry_path.is_file():
            raw = self.registry_path.read_text(encoding="utf-8", errors="ignore")
            for line in raw.splitlines():
                line_str = line.strip()
                if line_str.startswith("| `US-"):
                    m = re.search(r"\|\s*`US-(\d+)`\s*\|", line_str)
                    if m:
                        rows[int(m.group(1))] = line_str

        num_m = re.search(r"\d+", cid)
        curr_num = int(num_m.group(0)) if num_m else 0

        # Short persona for registry display
        short_persona = re.sub(r"\s*\([^)]*\)", "", persona).strip() or persona

        new_row = f"| `{cid}` | {title} | {status} | {short_persona} | {feature} | `{governing_prd}` |"
        rows[curr_num] = new_row

        output_lines = header_lines[:]
        for _, row_text in sorted(rows.items()):
            output_lines.append(row_text)
        output_lines.append("")

        final_content = "\n".join(output_lines)
        tmp_path = self.registry_path.with_suffix(".tmp")
        tmp_path.write_text(final_content, encoding="utf-8")
        tmp_path.replace(self.registry_path)

    def trace(
        self,
        story_filter: str | None = None,
        prd_filter: str | None = None,
    ) -> StoryTraceReport:
        """Audits bidirectional traceability across Personas -> PRDs -> Stories -> Tasks -> Commits."""
        parser = SpecOpsParser(self.project_docs)
        data = parser.parse_all()

        harvester = GitMetadataHarvester(self.root_dir)
        git_map = harvester.harvest()

        # Build indexes
        personas_known = {p.name.lower() for p in data.personas}
        for p in data.personas:
            personas_known.add(p.id.lower())
            first_name = p.name.split()[0].lower()
            personas_known.add(first_name)

        prds_by_id = {p.id: p for p in data.prds}
        stories_by_id = {s.id: s for s in data.stories}

        # Map stories to implementing tasks
        story_to_tasks: dict[str, list[Task]] = {s.id: [] for s in data.stories}
        unlinked_tasks: list[str] = []

        for task in data.tasks:
            linked_any = False
            for sid in task.governing_stories:
                norm_sid = normalize_story_id(sid, "US")
                if norm_sid in story_to_tasks:
                    story_to_tasks[norm_sid].append(task)
                    linked_any = True
                elif norm_sid in stories_by_id:
                    story_to_tasks.setdefault(norm_sid, []).append(task)
                    linked_any = True
            if not linked_any and not task.governing_stories:
                unlinked_tasks.append(task.canonical_id)

        orphaned_stories: list[str] = []
        broken_references: list[str] = []
        trace_items: list[StoryTraceItem] = []

        norm_story_filter = normalize_story_id(story_filter, "US") if story_filter else None
        norm_prd_filter = normalize_story_id(prd_filter, "PRD") if prd_filter else None

        for story in sorted(data.stories, key=lambda s: s.id):
            if norm_story_filter and story.id != norm_story_filter:
                continue
            if norm_prd_filter and story.governing_prd != norm_prd_filter:
                continue

            issues: list[str] = []

            # Check PRD linkage
            prd_clean = normalize_story_id(story.governing_prd, "PRD") if story.governing_prd else ""
            if not prd_clean or prd_clean not in prds_by_id:
                issue = f"Story {story.id} lacks valid governing PRD (got '{story.governing_prd}')"
                issues.append(issue)
                broken_references.append(issue)
                if story.id not in orphaned_stories:
                    orphaned_stories.append(story.id)

            # Check Persona linkage
            if story.persona:
                persona_s = story.persona.lower()
                matched_persona = any(pk in persona_s for pk in personas_known)
                if not matched_persona:
                    issue = f"Story {story.id} references unknown persona '{story.persona}'"
                    issues.append(issue)
                    broken_references.append(issue)
                    if story.id not in orphaned_stories:
                        orphaned_stories.append(story.id)
            else:
                issue = f"Story {story.id} lacks target persona"
                issues.append(issue)
                if story.id not in orphaned_stories:
                    orphaned_stories.append(story.id)

            tasks = story_to_tasks.get(story.id, [])
            task_ids = [t.canonical_id for t in tasks]

            # Collect commit hashes for tasks
            commits: list[str] = []
            for t in tasks:
                if t.canonical_id in git_map:
                    task_commits, _ = git_map[t.canonical_id]
                    commits.extend(c.hash for c in task_commits)
            commits = list(dict.fromkeys(commits))

            meta, _ = extract_frontmatter(story.raw_markdown) if story.raw_markdown else ({}, "")
            target_bc = str(meta.get("target_bc", ""))
            feature = str(meta.get("feature", story.feature))

            trace_items.append(
                StoryTraceItem(
                    id=story.id,
                    title=story.title,
                    status=story.status,
                    persona=story.persona,
                    governing_prd=story.governing_prd,
                    target_bc=target_bc,
                    feature=feature,
                    implementing_tasks=task_ids,
                    commits=commits,
                    issues=issues,
                )
            )

        covered = sum(1 for it in trace_items if it.is_covered)

        return StoryTraceReport(
            stories=trace_items,
            orphaned_stories=orphaned_stories,
            unlinked_tasks=unlinked_tasks,
            broken_references=broken_references,
            total_stories=len(trace_items),
            covered_stories=covered,
        )
