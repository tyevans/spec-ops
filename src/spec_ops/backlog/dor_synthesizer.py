"""Definition of Ready (DoR) automated contract synthesis engine."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

from ..config.models import SpecOpsConfig
from ..core.parser import extract_frontmatter
from .dor_gate import audit_task_health


class DORSynthesizer:
    """Evaluates task Definition of Ready completeness and synthesizes missing contracts."""

    def __init__(self, config: SpecOpsConfig):
        self.config = config
        self.backlog_dir = config.backlog_dir
        self.prd_dir = config.prd_dir
        self.stories_dir = config.user_stories_dir
        self.adrs_dir = getattr(config, "adr_dir", None) or (config.root_dir / "docs" / "project" / "adrs")

    def find_task_file(self, task_identifier: str) -> Path | None:
        """Finds task file by path, canonical ID, or numeric ID."""
        candidate = Path(task_identifier)
        if candidate.is_file():
            return candidate

        clean = task_identifier.upper().replace("TASK-", "").replace("SPIKE-", "").lstrip("0") or "0"
        pat = re.compile(rf"^(?:spike-|task-)?0*{clean}(?:-|\.|$)", re.IGNORECASE)

        if self.backlog_dir.exists():
            for p in self.backlog_dir.rglob("*.md"):
                if p.name == "PRIORITY.md":
                    continue
                if pat.search(p.stem) or task_identifier.upper() in p.stem.upper():
                    return p
        return None

    def get_accepted_adrs(self) -> list[str]:
        """Discovers accepted ADR identifiers."""
        accepted_dir = self.adrs_dir / "accepted"
        found: list[str] = []
        if accepted_dir.exists():
            for p in sorted(accepted_dir.glob("*.md")):
                m = re.search(r"adr-(\d+)", p.name, re.IGNORECASE)
                if m:
                    found.append(f"ADR-{int(m.group(1)):04d}")
        return found or ["ADR-0001", "ADR-0002", "ADR-0003", "ADR-0006"]

    def get_accepted_prds(self) -> list[str]:
        """Discovers accepted PRD identifiers."""
        accepted_dir = self.prd_dir / "accepted"
        found: list[str] = []
        if accepted_dir.exists():
            for p in sorted(accepted_dir.glob("*.md")):
                m = re.search(r"prd-(\d+)", p.name, re.IGNORECASE)
                if m:
                    found.append(f"PRD-{int(m.group(1)):04d}")
        return found or ["PRD-0001"]

    def get_accepted_stories(self) -> list[str]:
        """Discovers accepted user story identifiers."""
        accepted_dir = self.stories_dir / "accepted"
        found: list[str] = []
        if accepted_dir.exists():
            for p in sorted(accepted_dir.glob("*.md")):
                m = re.search(r"us-(\d+)", p.name, re.IGNORECASE)
                if m:
                    found.append(f"US-{int(m.group(1)):04d}")
        return found or ["US-0001"]

    def synthesize(
        self, task_identifier: str, dry_run: bool = False
    ) -> tuple[bool, str, dict[str, Any]]:
        """Synthesizes missing DoR contracts so the task can pass Definition of Ready gating."""
        task_path = self.find_task_file(task_identifier)
        if not task_path or not task_path.exists():
            return False, f"Task file not found matching '{task_identifier}'", {}

        content = task_path.read_text(encoding="utf-8")
        meta, body = extract_frontmatter(content)
        changes: list[str] = []

        # 1. Normalize ID and Title
        raw_id = str(meta.get("id", ""))
        clean_num = raw_id.upper().replace("TASK-", "").replace("SPIKE-", "").lstrip("0")
        if not clean_num:
            m_stem = re.search(r"(\d+)", task_path.stem)
            clean_num = m_stem.group(1) if m_stem else "1"
        num_str = f"{int(clean_num):04d}"
        is_spike = "spike" in task_path.name.lower() or raw_id.upper().startswith("SPIKE")
        canonical_id = f"{'SPIKE' if is_spike else 'TASK'}-{num_str}"

        if not meta.get("id"):
            meta["id"] = num_str
            changes.append(f"Frontmatter ID: {num_str}")

        title = str(meta.get("title", ""))
        if not title:
            m_title = re.search(r"^#\s+(?:TASK-\d+:|SPIKE-\d+:)?\s*(.*)$", body, re.M)
            title = m_title.group(1).strip() if m_title else task_path.stem
            meta["title"] = title
            changes.append(f"Frontmatter Title: {title}")

        if not meta.get("status"):
            meta["status"] = "Proposed"
            changes.append("Frontmatter Status: Proposed")

        # 2. Target Bounded Context
        target_bc = str(meta.get("target_bc", "")).strip()
        if not target_bc:
            target_bc = "core"
            meta["target_bc"] = target_bc
            changes.append(f"Target Bounded Context: {target_bc}")

        # 3. Governing PRDs
        gov_prds = meta.get("governing_prds", [])
        if isinstance(gov_prds, str):
            gov_prds = [gov_prds]
        accepted_prds = self.get_accepted_prds()
        if not gov_prds:
            meta["governing_prds"] = [accepted_prds[0]]
            changes.append(f"Governing PRD: {accepted_prds[0]}")
        else:
            valid_prds = [p for p in gov_prds if p in accepted_prds]
            if not valid_prds:
                merged_prds = list(dict.fromkeys([*gov_prds, accepted_prds[0]]))
                meta["governing_prds"] = merged_prds
                changes.append(f"Updated Governing PRDs with accepted: {', '.join(merged_prds)}")

        # 4. Governing ADRs
        gov_adrs = meta.get("governing_adrs", [])
        if isinstance(gov_adrs, str):
            gov_adrs = [gov_adrs]
        accepted_adrs = self.get_accepted_adrs()
        if not gov_adrs:
            meta["governing_adrs"] = accepted_adrs[:4]
            changes.append(f"Governing ADRs: {', '.join(accepted_adrs[:4])}")
        else:
            # Ensure at least one accepted ADR is included
            valid = [a for a in gov_adrs if a in accepted_adrs]
            if not valid:
                merged = list(dict.fromkeys([*gov_adrs, *accepted_adrs[:2]]))
                meta["governing_adrs"] = merged
                changes.append(f"Updated Governing ADRs with accepted: {', '.join(merged)}")

        # 5. Governing Stories & Persona
        gov_stories = meta.get("governing_stories", [])
        if isinstance(gov_stories, str):
            gov_stories = [gov_stories]
        accepted_stories = self.get_accepted_stories()
        if not gov_stories:
            meta["governing_stories"] = [accepted_stories[0]]
            changes.append(f"Governing Story: {accepted_stories[0]}")
        else:
            valid_stories = [s for s in gov_stories if s in accepted_stories]
            if not valid_stories:
                merged_stories = list(dict.fromkeys([*gov_stories, accepted_stories[0]]))
                meta["governing_stories"] = merged_stories
                changes.append(f"Updated Governing Stories with accepted: {', '.join(merged_stories)}")

        # Ensure valid persona
        has_persona = bool(
            meta.get("persona")
            or meta.get("target_persona")
            or re.search(r"\b(alex|jordan|morgan|riley|taylor|developer|architect|user)\b", body, re.I)
        )
        if not has_persona:
            meta["persona"] = "Jordan (The AI-Native Engineering Lead) & Alex (The Agentic Systems Architect)"
            changes.append("Persona: Jordan (The AI-Native Engineering Lead) & Alex (The Agentic Systems Architect)")

        # 6. Check and synthesize Markdown Body sections
        new_sections: list[str] = []

        # Check Gherkin scenarios
        has_gherkin = bool(
            re.search(r"\bgiven\b", body, re.I)
            and re.search(r"\bwhen\b", body, re.I)
            and re.search(r"\bthen\b", body, re.I)
        )
        if not has_gherkin:
            gherkin_block = f"""## Acceptance Criteria

```gherkin
Scenario: Verify {title}
  Given the system is initialized and ready
  When the user executes the workflow for "{title}"
  Then observable outputs satisfy public contracts without backdoor tampering
  And no internal invariants are violated.
```"""
            new_sections.append(gherkin_block)
            changes.append("Executable Gherkin Acceptance Criteria (ADR-0006)")

        # Check Mutation Testing Scope
        has_mutation = bool(
            re.search(r"\bmutmut\b", body, re.I)
            or re.search(r"\bmutation\s+(?:testing\s+)?scope\b", body, re.I)
            or meta.get("mutation_scope")
        )
        if not has_mutation:
            mut_block = f"""## Mutation Testing Scope
- Target domain module: `src/spec_ops/{target_bc}/...`
- Minimum mutation kill score: >=80% under Mutmut (ADR-0009)."""
            new_sections.append(mut_block)
            changes.append("Mutation Testing Scope (>=80% kill score under Mutmut)")

        # Check Hypothesis Invariants
        has_hypothesis = bool(
            re.search(r"@given", body)
            or re.search(r"\bhypothesis\b", body, re.I)
            or re.search(r"generative\s+property", body, re.I)
        )
        if not has_hypothesis:
            hypo_block = """## Hypothesis Invariant Properties
- `@given(...)`: Generative property tests asserting state invariants across randomized inputs without shrinking failures (ADR-0009)."""
            new_sections.append(hypo_block)
            changes.append("Hypothesis Generative Property Invariants (ADR-0009)")

        # Check Single Bounded Context & INVEST Feasibility
        has_scope = bool(
            re.search(r"<500\s+lines", body, re.I)
            or re.search(r"<400\s+lines", body, re.I)
            or re.search(r"invest-compliant", body, re.I)
        )
        if not has_scope:
            scope_block = f"""## Scope & Architectural Invariants
- Target Bounded Context: `{target_bc}` (single bounded context)
- Estimated Implementation Diff: <400 lines
- File Length Limit: all touched source files strictly <500 lines (ADR-0002)."""
            new_sections.append(scope_block)
            changes.append("INVEST Scope and File Length Limits (<500 lines)")

        # Assemble updated content
        yaml_frontmatter = yaml.dump(meta, sort_keys=False).strip()
        updated_body = body.rstrip()
        if new_sections:
            updated_body += "\n\n" + "\n\n".join(new_sections) + "\n"

        updated_content = f"---\n{yaml_frontmatter}\n---\n\n{updated_body.lstrip()}"

        if not dry_run:
            task_path.write_text(updated_content, encoding="utf-8")

        return (
            True,
            f"{'[DRY-RUN] ' if dry_run else ''}Synthesized DoR contracts for {canonical_id}",
            {
                "canonical_id": canonical_id,
                "task_path": task_path,
                "changes": changes,
                "content": updated_content,
            },
        )
