"""Deterministic lifecycle stage-gate engine and registry synchronization for PRDs."""

from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..core.parser import SpecOpsParser, extract_frontmatter
from .linter import PRDLinter


class PRDLifecycleManager:
    """Manages PRD lifecycle stage promotions and atomic registry synchronization."""

    STAGES: list[str] = ["idea", "shaped", "accepted", "shipped"]

    def __init__(self, config: SpecOpsConfig):
        self.config = config
        self.prd_dir = config.prd_dir
        self.registry_path = config.prd_dir / "REGISTRY.md"
        self.roadmap_path = config.backlog_dir / "ROADMAP.md"

    def find_prd_file(self, prd_id_or_path: str | Path) -> Path | None:
        """Locates PRD document across stages or by direct path."""
        candidate = Path(prd_id_or_path)
        if candidate.is_file():
            return candidate.resolve()

        raw = str(prd_id_or_path).strip().upper()
        if raw.startswith("PRD"):
            num = raw[3:].lstrip("-")
            clean_id = f"PRD-{num.zfill(4)}" if num.isdigit() else raw
        elif raw.isdigit():
            clean_id = f"PRD-{raw.zfill(4)}"
        else:
            clean_id = raw

        clean_num = clean_id.replace("PRD-", "")

        if self.prd_dir.exists():
            for p in self.prd_dir.rglob("*.md"):
                if p.name == "REGISTRY.md":
                    continue
                if f"PRD-{clean_num}" in p.stem.upper():
                    return p.resolve()
                meta, _ = extract_frontmatter(p.read_text(encoding="utf-8"))
                if str(meta.get("id", "")).strip().upper() in (clean_num, clean_id):
                    return p.resolve()
        return None

    def update_registry(
        self,
        prd_id: str,
        title: str,
        status: str,
        persona: str,
        component: str,
    ) -> None:
        """Atomically updates docs/project/product/REGISTRY.md table."""
        if not self.registry_path.exists():
            self.registry_path.parent.mkdir(parents=True, exist_ok=True)
            header = (
                "# PRD Registry\n\n"
                "| ID | Title | Status | Target Persona | Component |\n"
                "|---|---|---|---|---|\n"
            )
            self.registry_path.write_text(header, encoding="utf-8")

        lines = self.registry_path.read_text(encoding="utf-8").splitlines()
        new_lines: list[str] = []
        found = False
        clean_id = prd_id.upper()

        for line in lines:
            parts = [c.strip() for c in line.strip().split("|")]
            if len(parts) == 7 and parts[1].replace("`", "").upper() == clean_id:
                curr_title = title or parts[2]
                curr_persona = persona or parts[4]
                curr_component = component or parts[5]
                new_lines.append(
                    f"| `{clean_id}` | {curr_title} | {status} | {curr_persona} | {curr_component} |"
                )
                found = True
            else:
                new_lines.append(line)

        if not found:
            new_row = f"| `{clean_id}` | {title} | {status} | {persona} | {component} |"
            new_lines.append(new_row)

        self.registry_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    def update_roadmap(self, prd_id: str, title: str) -> None:
        """Records milestone completion date and closes horizon in ROADMAP.md."""
        if not self.roadmap_path.exists():
            return

        content = self.roadmap_path.read_text(encoding="utf-8")
        today = date.today().isoformat()
        completion_entry = (
            f"- Milestone completion date: {today} (Horizon closed for {prd_id} — {title})."
        )
        if completion_entry not in content:
            updated = content.rstrip() + f"\n\n{completion_entry}\n"
            self.roadmap_path.write_text(updated, encoding="utf-8")

    def promote(self, prd_id_or_path: str | Path, target_stage: str) -> tuple[bool, str]:
        """Evaluates quality gates and advances PRD to target lifecycle stage."""
        stage_norm = target_stage.strip().lower()
        if stage_norm not in self.STAGES:
            return (
                False,
                f"❌ Invalid target stage '{target_stage}'. Must be one of: {', '.join(self.STAGES)}",
            )

        prd_file = self.find_prd_file(prd_id_or_path)
        if not prd_file:
            return False, f"❌ PRD not found: {prd_id_or_path}"

        content = prd_file.read_text(encoding="utf-8")
        meta, _ = extract_frontmatter(content)
        raw_id = str(meta.get("id", prd_file.stem))
        clean_num = raw_id.split("-")[-1].zfill(4)
        canonical_id = f"PRD-{clean_num}"
        title = str(meta.get("title", prd_file.stem))
        persona = str(meta.get("target_persona", ""))
        component = str(meta.get("component", "core"))

        if stage_norm == "shaped":
            has_pain_points = any(
                re.search(
                    r"^##\s+(Who this is for|Problem Statement|What the person cannot do today)",
                    line,
                    re.IGNORECASE,
                )
                for line in content.splitlines()
            )
            if not has_pain_points:
                return (
                    False,
                    f"❌ Stage-gate violation error: PRD {canonical_id} must define user pain points before promotion to shaped.",
                )

        elif stage_norm == "accepted":
            missing_prereqs: list[str] = []
            if not persona.strip() or persona.strip().lower() in ("unmapped", "none", "unknown"):
                missing_prereqs.append("Target persona unmapped")

            linter = PRDLinter(self.config.root_dir)
            lint_res = linter.lint_file(prd_file)

            no_outcomes = any(
                v.message == "No checkable outcomes defined" for v in lint_res.violations
            )
            missing_section = any(
                v.message == "Missing required section: '## Checkable Outcomes'"
                for v in lint_res.violations
            )
            if no_outcomes or missing_section or len(lint_res.outcome_checks) == 0:
                missing_prereqs.append("No checkable outcomes defined")
            else:
                unfalsifiable = [oc for oc in lint_res.outcome_checks if not oc.is_falsifiable]
                if unfalsifiable:
                    missing_prereqs.append("Checkable outcomes contain unfalsifiable language")

            if missing_prereqs:
                err_lines = [
                    f"❌ Stage-gate violation error: Promotion to 'accepted' blocked for {canonical_id}:",
                    "Missing prerequisites:",
                ]
                for p in missing_prereqs:
                    err_lines.append(f"   - {p}")
                return False, "\n".join(err_lines)

        elif stage_norm == "shipped":
            parser = SpecOpsParser(self.config.project_docs_dir)
            p_data = parser.parse_all()
            prd_tasks = [
                t
                for t in p_data.tasks
                if canonical_id in t.governing_prds
                or canonical_id.replace("PRD-", "") in t.governing_prds
            ]
            incomplete = [t.canonical_id for t in prd_tasks if t.status != "Complete"]
            if incomplete:
                return (
                    False,
                    f"❌ Stage-gate violation error: Cannot ship {canonical_id}: "
                    f"Implementing tasks are not complete ({', '.join(incomplete)}).",
                )

        target_dir = self.prd_dir / stage_norm
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / prd_file.name

        lines = content.splitlines()
        new_lines: list[str] = []
        for line in lines:
            if re.match(r"^status:\s*", line, re.IGNORECASE):
                new_lines.append(f"status: {stage_norm.capitalize()}")
            else:
                new_lines.append(line)
        new_content = "\n".join(new_lines) + "\n"

        target_file.write_text(new_content, encoding="utf-8")
        if prd_file.resolve() != target_file.resolve():
            prd_file.unlink()

        self.update_registry(
            canonical_id,
            title,
            stage_norm.capitalize(),
            persona,
            component,
        )

        if stage_norm == "shipped":
            self.update_roadmap(canonical_id, title)

        return True, f"✅ Successfully promoted {canonical_id} to '{stage_norm}' at {target_file}"

    def ship(self, prd_id_or_path: str | Path) -> tuple[bool, str]:
        """Convenience wrapper for promoting an accepted PRD to shipped via shipping gate."""
        from .shipping import ship_prd

        return ship_prd(self.config, prd_id_or_path)

