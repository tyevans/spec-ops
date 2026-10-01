"""INVEST-compliant task decomposition and architectural spike identification engine."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from ..config.models import SpecOpsConfig
from ..core.parser import extract_frontmatter
from ..spike.scaffold import create_spike, find_next_spike_number
from .delta import (
    CheckableOutcome,
    find_existing_stories,
    parse_checkable_outcomes,
    validate_falsifiability,
)
from .synthesis import append_to_priority, update_prd_links

SPIKE_KEYWORDS = (
    "spike",
    "prototype",
    "benchmark",
    "uncertain",
    "explore",
    "evaluate",
    "feasibility",
    "investigate",
    "risk",
    "tradeoff",
    "architectural uncertainty",
    "ast seam",
    "algorithm",
)


def slugify(text: str) -> str:
    """Generates a clean filesystem-safe slug from a title."""
    cleaned = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", cleaned).strip("-")
    slug = re.sub(r"-+", "-", slug)
    return slug[:50] or "task"


class INVESTDecomposer:
    """Decomposes PRDs into INVEST-compliant vertical tasks and architectural spikes."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config
        self.prd_dir = config.prd_dir
        self.backlog_dir = config.backlog_dir
        self.stories_dir = config.user_stories_dir
        self.adrs_dir = getattr(config, "adr_dir", None) or (config.root_dir / "docs" / "project" / "adrs")

    def find_prd_file(self, prd_identifier: str) -> Path | None:
        """Finds the PRD markdown file matching the given identifier."""
        clean = prd_identifier.upper().replace("PRD-", "").lstrip("0") or "0"
        target_pat = re.compile(rf"prd-0*{clean}(?:-|\.|$)", re.IGNORECASE)
        if self.prd_dir.exists():
            for p in self.prd_dir.rglob("*.md"):
                if target_pat.search(p.name):
                    return p
        return None

    def get_next_task_number(self, target_dir: Path | None = None) -> int:
        """Calculates next sequential task number across backlog and PRIORITY.md."""
        max_id = 0
        dirs_to_check = [self.backlog_dir]
        if target_dir and target_dir not in dirs_to_check:
            dirs_to_check.append(target_dir)

        for d in dirs_to_check:
            if d.exists():
                for p in d.rglob("*.md"):
                    m = re.match(r"^(\d+)", p.stem)
                    if m:
                        max_id = max(max_id, int(m.group(1)))

        p_file = self.backlog_dir / "PRIORITY.md"
        if p_file.is_file():
            try:
                content = p_file.read_text(encoding="utf-8")
                for m in re.finditer(r"TASK-(\d+)", content):
                    max_id = max(max_id, int(m.group(1)))
            except OSError:
                pass

        return max_id + 1

    def get_accepted_adrs(self) -> list[str]:
        """Discovers accepted ADR identifiers from the repository."""
        accepted_dir = self.adrs_dir / "accepted"
        found: list[str] = []
        if accepted_dir.exists():
            for p in sorted(accepted_dir.glob("*.md")):
                m = re.search(r"adr-(\d+)", p.name, re.IGNORECASE)
                if m:
                    found.append(f"ADR-{int(m.group(1)):04d}")
        if not found:
            found = ["ADR-0001", "ADR-0002", "ADR-0003", "ADR-0006"]
        return found

    def is_architectural_spike_candidate(self, text: str) -> bool:
        """Detects whether an outcome contains architectural uncertainty requiring a spike."""
        lower = text.lower()
        return any(re.search(rf"\b{kw}\b", lower) for kw in SPIKE_KEYWORDS)

    def decompose(
        self,
        prd_identifier: str,
        output_dir: Path | str | None = None,
        dry_run: bool = False,
    ) -> list[dict[str, Any]]:
        """Decomposes a PRD into INVEST vertical tasks and architectural spikes."""
        prd_file = self.find_prd_file(prd_identifier)
        if not prd_file or not prd_file.exists():
            raise FileNotFoundError(f"PRD not found matching identifier: {prd_identifier}")

        content = prd_file.read_text(encoding="utf-8")
        meta, _ = extract_frontmatter(content)

        prd_title = str(meta.get("title", prd_file.stem))
        persona = str(
            meta.get("target_persona")
            or meta.get("persona")
            or "Alex (The Agentic Systems Architect) & Jordan (The AI-Native Engineering Lead)"
        )
        component = str(meta.get("component") or meta.get("target_bc") or "core")
        clean_prd_num = str(meta.get("id", "0001")).replace("PRD-", "").lstrip("0") or "1"
        prd_canonical_id = f"PRD-{int(clean_prd_num):04d}"

        outcomes = parse_checkable_outcomes(content)
        if not outcomes:
            outcomes = [
                CheckableOutcome(
                    id=1,
                    raw_text=prd_title,
                    clean_text=prd_title,
                    is_falsifiable=True,
                )
            ]

        # Find existing linked stories
        existing_stories = find_existing_stories(self.stories_dir, prd_canonical_id)
        story_ids = [s["id"] for s in existing_stories]
        if not story_ids:
            gov_stories = meta.get("governing_stories", [])
            if isinstance(gov_stories, str):
                gov_stories = [gov_stories]
            story_ids = gov_stories or ["US-0001"]

        accepted_adrs = self.get_accepted_adrs()
        gov_adrs = meta.get("governing_adrs", [])
        if isinstance(gov_adrs, str):
            gov_adrs = [gov_adrs]
        combined_adrs = list(dict.fromkeys([*gov_adrs, *accepted_adrs]))[:4]

        dest_dir = Path(output_dir) if output_dir else (self.backlog_dir / "proposed")
        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)

        results: list[dict[str, Any]] = []
        created_task_ids: list[str] = []
        created_task_files: list[Path] = []
        curr_task_num = self.get_next_task_number(dest_dir) - 1

        for idx, outcome in enumerate(outcomes):
            outcome_text = outcome.clean_text
            story_id = story_ids[idx % len(story_ids)]
            spike_id: str | None = None

            # Detect architectural uncertainty
            if self.is_architectural_spike_candidate(outcome_text):
                spike_num = find_next_spike_number(self.config.root_dir)
                spike_id = f"SPIKE-{spike_num:04d}"
                spike_slug = slugify(f"spike-{outcome_text}")
                spike_file = dest_dir / f"{spike_num:04d}-{spike_slug}.md"
                spike_title = f"Architectural Spike: Explore and benchmark {outcome_text}"

                spike_meta = {
                    "id": f"{spike_num:04d}",
                    "title": spike_title,
                    "status": "Proposed",
                    "target_bc": component,
                    "governing_prds": [prd_canonical_id],
                    "governing_stories": [story_id],
                    "governing_adrs": combined_adrs,
                }
                spike_body = f"""# {spike_id}: {spike_title}

## Summary & Unanswered Question
Empirically evaluate feasibility and performance trade-offs for: {outcome_text}.
Governing Persona: {persona}

## Timebox & Scope
- **Timebox**: 2h
- **Target Harness**: `spikes/spike_{spike_num:04d}/`
- **Target Bounded Context**: `{component}`

## Acceptance Criteria

```gherkin
Scenario: Validate empirical hypothesis for {outcome_text}
  Given an isolated benchmark harness in "spikes/spike_{spike_num:04d}/"
  When the prototype benchmark is executed
  Then observable results clarify architectural trade-offs without breaking invariants.
```

## Mutation Testing Scope
- Target domain module: `src/spec_ops/{component}/...`
- Minimum mutation kill score: >=80% under Mutmut (ADR-0009).

## Hypothesis Invariant Properties
- `@given(...)`: Generative property tests asserting state invariants across randomized inputs without shrinking failures (ADR-0009).
"""
                spike_content = f"---\n{yaml.dump(spike_meta, sort_keys=False).strip()}\n---\n\n{spike_body}\n"
                results.append(
                    {
                        "id": spike_id,
                        "title": spike_title,
                        "path": spike_file,
                        "is_spike": True,
                        "content": spike_content,
                    }
                )

                if not dry_run:
                    spike_file.write_text(spike_content, encoding="utf-8")
                    created_task_ids.append(spike_id)
                    created_task_files.append(spike_file)
                    # Scaffold benchmark harness in spikes/spike_XXXX/
                    harness_dir = self.config.root_dir / "spikes" / f"spike_{spike_num:04d}"
                    harness_dir.mkdir(parents=True, exist_ok=True)
                    (harness_dir / "__init__.py").write_text("", encoding="utf-8")
                    (harness_dir / f"test_spike_{spike_num:04d}.py").write_text(
                        f'"""Empirical benchmark for {spike_id}."""\n\ndef test_hypothesis():\n    assert True\n',
                        encoding="utf-8",
                    )

            # Generate INVEST vertical slice task
            curr_task_num += 1
            task_id = f"TASK-{curr_task_num:04d}"
            task_title = f"Implement {outcome_text}"
            task_slug = slugify(outcome_text)
            task_file = dest_dir / f"{curr_task_num:04d}-{task_slug}.md"

            deps = [spike_id] if spike_id else []
            task_meta = {
                "id": f"{curr_task_num:04d}",
                "title": task_title,
                "status": "Proposed",
                "dependencies": deps,
                "governing_adrs": combined_adrs,
                "governing_prds": [prd_canonical_id],
                "governing_stories": [story_id],
                "target_bc": component,
            }

            task_body = f"""# {task_id}: {task_title}

## Summary
Fulfills Outcome {outcome.id} of {prd_canonical_id} for persona {persona}.
Target capability: {outcome_text}.

## Problem Statement & Context
Delivers an INVEST-compliant vertical slice in bounded context `{component}`.
Estimated implementation diff: <400 lines.
File length limit: all touched source files strictly <500 lines (ADR-0002).

## Acceptance Criteria

```gherkin
Scenario: Verify {outcome_text}
  Given the system is initialized and ready
  When the user executes the workflow for "{task_title}"
  Then observable outputs satisfy public contracts without backdoor tampering
  And no internal invariants are violated.
```

## Mutation Testing Scope
- Target domain module: `src/spec_ops/{component}/...`
- Minimum mutation kill score: >=80% under Mutmut (ADR-0009).

## Hypothesis Invariant Properties
- `@given(...)`: Generative property tests asserting state invariants across randomized inputs without shrinking failures (ADR-0009).

## Definition of Done (Blackbox Frontdoor TDD)
1. Public interfaces or standard domain contracts implemented.
2. Verified via automated blackbox tests without private backdoor manipulation (ADR-0003).
3. All new source files strictly under 500 lines (ADR-0002).
"""
            task_content = f"---\n{yaml.dump(task_meta, sort_keys=False).strip()}\n---\n\n{task_body}\n"
            results.append(
                {
                    "id": task_id,
                    "title": task_title,
                    "path": task_file,
                    "is_spike": False,
                    "content": task_content,
                }
            )

            if not dry_run:
                task_file.write_text(task_content, encoding="utf-8")
                created_task_ids.append(task_id)
                created_task_files.append(task_file)

        if not dry_run and output_dir is None:
            append_to_priority(self.backlog_dir, created_task_ids, created_task_files)
            update_prd_links(prd_file, story_ids, created_task_ids)

        return results
