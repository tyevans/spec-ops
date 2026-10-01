"""Interactive Persona Customer Journey Map and Pain Point Matrix Visualizer."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

import yaml

from ..config.models import SpecOpsConfig
from ..core.persona_models import PersonaDocument, PersonaProfile
from .journey_html import render_journey_map_html

ACCEPTED_STATUSES = {"accepted", "shipped", "complete", "done", "graduated"}
STOP_WORDS = {"when", "that", "with", "from", "have", "this", "they", "will", "what", "their", "there", "about", "which"}


@dataclass
class PainPointRecord:
    persona_id: str
    persona_name: str
    index: int
    description: str
    is_addressed: bool
    linked_stories: list[str] = field(default_factory=list)
    linked_prds: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "persona_id": self.persona_id,
            "persona_name": self.persona_name,
            "index": self.index,
            "description": self.description,
            "is_addressed": self.is_addressed,
            "status": "Addressed" if self.is_addressed else "Unaddressed",
            "linked_stories": list(self.linked_stories),
            "linked_prds": list(self.linked_prds),
        }


@dataclass
class PersonaJourneyMap:
    persona_id: str
    persona_name: str
    role: str
    total_pain_points: int
    addressed_pain_points: int
    unaddressed_pain_points: int
    coverage_percentage: float
    pain_points: list[PainPointRecord] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.persona_id,
            "name": self.persona_name,
            "role": self.role,
            "total_pain_points": self.total_pain_points,
            "addressed_pain_points": self.addressed_pain_points,
            "unaddressed_pain_points": self.unaddressed_pain_points,
            "coverage_percentage": round(self.coverage_percentage, 1),
            "pain_points": [p.to_dict() for p in self.pain_points],
        }


@dataclass
class CustomerJourneyReport:
    total_personas: int
    total_pain_points: int
    addressed_pain_points: int
    unaddressed_pain_points: int
    overall_coverage_percentage: float
    personas: list[PersonaJourneyMap] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "summary": {
                "total_personas": self.total_personas,
                "total_pain_points": self.total_pain_points,
                "addressed_pain_points": self.addressed_pain_points,
                "unaddressed_pain_points": self.unaddressed_pain_points,
                "overall_coverage_percentage": round(self.overall_coverage_percentage, 1),
            },
            "personas": [p.to_dict() for p in self.personas],
        }


def _extract_tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-zA-Z0-9_-]{4,}", text.lower()) if w not in STOP_WORDS}


def _clean_id(raw_id: str, prefix: str) -> str:
    clean = re.sub(rf"^{prefix}-?", "", str(raw_id), flags=re.IGNORECASE).lstrip("0")
    return f"{prefix}-{clean.zfill(4)}" if clean else str(raw_id).upper()


def _is_accepted(status: str) -> bool:
    return str(status).strip().lower() in ACCEPTED_STATUSES


class JourneyMapEngine:
    """Correlates personas, pain points, PRDs, and executable user stories."""

    def __init__(self, repo_root: Path | str | None = None, config: SpecOpsConfig | None = None) -> None:
        if config is not None:
            self.root_dir = Path(config.root_dir).resolve()
        elif repo_root is not None:
            self.root_dir = Path(repo_root).resolve()
        else:
            self.root_dir = Path.cwd().resolve()

    def parse_personas(self) -> list[PersonaProfile]:
        candidates = [
            self.root_dir / "docs" / "project" / "user_stories" / "PERSONAS.md",
            self.root_dir / "docs" / "user_stories" / "PERSONAS.md",
        ]
        p_file = next((c for c in candidates if c.is_file()), None)
        return PersonaDocument.parse(p_file.read_text(encoding="utf-8")).personas if p_file else []

    def parse_stories(self) -> list[dict[str, Any]]:
        stories_dir = self.root_dir / "docs" / "project" / "user_stories"
        if not stories_dir.is_dir():
            stories_dir = self.root_dir / "docs" / "user_stories"
        if not stories_dir.is_dir():
            return []

        stories: list[dict[str, Any]] = []
        for path in sorted(stories_dir.rglob("*.md")):
            if path.name == "PERSONAS.md":
                continue
            content = path.read_text(encoding="utf-8")
            fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            fm: dict[str, Any] = {}
            if fm_match:
                try:
                    fm = yaml.safe_load(fm_match.group(1)) or {}
                except Exception:
                    pass
            s_id = fm.get("id") or path.stem
            stories.append({
                "id": _clean_id(str(s_id), "US"),
                "title": fm.get("title", path.stem),
                "persona": fm.get("persona") or fm.get("target_persona", ""),
                "status": fm.get("status", "Accepted"),
                "governing_prd": fm.get("governing_prd") or fm.get("prd", ""),
                "pain_point": fm.get("pain_point"),
                "pain_points": fm.get("pain_points") or fm.get("addressed_pain_points", []),
                "content": content,
            })
        return stories

    def parse_prds(self) -> list[dict[str, Any]]:
        prd_dir = self.root_dir / "docs" / "project" / "product"
        if not prd_dir.is_dir():
            prd_dir = self.root_dir / "docs" / "product"
        if not prd_dir.is_dir():
            return []

        prds: list[dict[str, Any]] = []
        for path in sorted(prd_dir.rglob("*.md")):
            content = path.read_text(encoding="utf-8")
            fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
            fm: dict[str, Any] = {}
            if fm_match:
                try:
                    fm = yaml.safe_load(fm_match.group(1)) or {}
                except Exception:
                    pass
            p_id = fm.get("id") or path.stem
            prds.append({
                "id": _clean_id(str(p_id), "PRD"),
                "title": fm.get("title", path.stem),
                "status": fm.get("status", "Accepted"),
                "persona": fm.get("target_persona") or fm.get("persona", ""),
            })
        return prds

    def _matches_story_to_pain_point(
        self, story: dict[str, Any], persona: PersonaProfile, pp_idx: int, pp_text: str
    ) -> bool:
        s_persona = str(story.get("persona", "")).lower()
        if persona.name.lower() not in s_persona and persona.id.lower() not in s_persona:
            return False

        explicit = story.get("pain_point")
        if explicit is not None and (explicit == pp_idx or str(explicit).strip() == str(pp_idx) or str(explicit).lower().strip() in pp_text.lower()):
            return True

        for item in story.get("pain_points") or []:
            if item == pp_idx or str(item).strip() == str(pp_idx) or str(item).lower().strip() in pp_text.lower():
                return True

        body = (str(story.get("title", "")) + " " + str(story.get("content", ""))).lower()
        if pp_text.lower() in body or f"pain point {pp_idx}" in body or f"pain point #{pp_idx}" in body:
            return True

        pp_tokens = _extract_tokens(pp_text)
        if len(pp_tokens) >= 2:
            common = pp_tokens.intersection(_extract_tokens(body))
            if len(common) >= 2 and len(common) / len(pp_tokens) >= 0.35:
                return True
        return False

    def correlate(
        self,
        persona_filter: str | None = None,
        personas_list: list[PersonaProfile] | None = None,
        stories_list: list[dict[str, Any]] | None = None,
        prds_list: list[dict[str, Any]] | None = None,
    ) -> CustomerJourneyReport:
        personas = personas_list if personas_list is not None else self.parse_personas()
        stories = stories_list if stories_list is not None else self.parse_stories()
        _ = prds_list if prds_list is not None else self.parse_prds()

        filter_clean = persona_filter.strip().lower() if persona_filter else None
        mapped_personas: list[PersonaJourneyMap] = []
        total_pts = 0
        addr_pts = 0

        for p in personas:
            if filter_clean and (filter_clean != p.id.lower() and filter_clean not in p.name.lower() and p.name.lower() not in filter_clean):
                continue

            p_records: list[PainPointRecord] = []
            p_addr = 0
            p_total = len(p.pain_points)

            for idx, pt_desc in enumerate(p.pain_points, start=1):
                linked_stories = []
                linked_prds = []
                is_addressed = False

                for s in stories:
                    if self._matches_story_to_pain_point(s, p, idx, pt_desc):
                        if s["id"] not in linked_stories:
                            linked_stories.append(s["id"])
                        if s.get("governing_prd"):
                            prd_clean = _clean_id(s["governing_prd"], "PRD")
                            if prd_clean not in linked_prds:
                                linked_prds.append(prd_clean)
                        if _is_accepted(s.get("status", "")):
                            is_addressed = True

                if is_addressed:
                    p_addr += 1

                p_records.append(
                    PainPointRecord(
                        persona_id=p.id,
                        persona_name=p.name,
                        index=idx,
                        description=pt_desc,
                        is_addressed=is_addressed,
                        linked_stories=linked_stories,
                        linked_prds=linked_prds,
                    )
                )

            cov = 100.0 if p_total == 0 else max(0.0, min(100.0, (p_addr / p_total) * 100.0))
            if not math.isfinite(cov):
                cov = 0.0

            mapped_personas.append(
                PersonaJourneyMap(
                    persona_id=p.id,
                    persona_name=p.name,
                    role=p.role,
                    total_pain_points=p_total,
                    addressed_pain_points=p_addr,
                    unaddressed_pain_points=p_total - p_addr,
                    coverage_percentage=cov,
                    pain_points=p_records,
                )
            )
            total_pts += p_total
            addr_pts += p_addr

        overall_cov = 100.0 if total_pts == 0 else max(0.0, min(100.0, (addr_pts / total_pts) * 100.0))
        if not math.isfinite(overall_cov):
            overall_cov = 0.0

        return CustomerJourneyReport(
            total_personas=len(mapped_personas),
            total_pain_points=total_pts,
            addressed_pain_points=addr_pts,
            unaddressed_pain_points=total_pts - addr_pts,
            overall_coverage_percentage=overall_cov,
            personas=mapped_personas,
        )

    def format_markdown(self, report: CustomerJourneyReport) -> str:
        lines = [
            "=== SpecOps Persona Customer Journey Map & Pain Point Matrix ===",
            f"Overall Journey Coverage: {report.overall_coverage_percentage:.1f}% "
            f"({report.addressed_pain_points}/{report.total_pain_points} pain points addressed across {report.total_personas} persona(s))\n",
        ]
        for p in report.personas:
            lines.extend([
                f"## Persona: {p.persona_name} — {p.role}",
                f"Coverage: {p.coverage_percentage:.1f}% ({p.addressed_pain_points}/{p.total_pain_points} pain points addressed)\n",
                "| # | Pain Point | Status | Linked Stories | Linked PRDs |",
                "|---|---|---|---|---|",
            ])
            for pt in p.pain_points:
                st = "✅ Addressed" if pt.is_addressed else "⚠️ Unaddressed"
                lines.append(f"| {pt.index} | {pt.description} | {st} | {', '.join(pt.linked_stories) or '—'} | {', '.join(pt.linked_prds) or '—'} |")
            lines.append("")
        return "\n".join(lines).strip()

    def format_json(self, report: CustomerJourneyReport, indent: int = 2) -> str:
        return json.dumps(report.to_dict(), indent=indent)

    def generate_html(self, report: CustomerJourneyReport) -> str:
        return render_journey_map_html(report)

    def export_html(self, report: CustomerJourneyReport, output_path: Path | str | None = None) -> Path:
        html_doc = self.generate_html(report)
        out_file = Path(output_path).resolve() if output_path else self.root_dir / "dist" / "journey" / "customer-journey-map.html"
        out_file.parent.mkdir(parents=True, exist_ok=True)
        out_file.write_text(html_doc, encoding="utf-8")
        return out_file


def handle_journey_command(
    config: SpecOpsConfig,
    persona: str | None = None,
    fmt: str = "markdown",
    output: str | None = None,
) -> int:
    engine = JourneyMapEngine(config=config, repo_root=config.root_dir)
    report = engine.correlate(persona_filter=persona)

    if fmt == "json":
        text = engine.format_json(report)
        if output:
            out_p = Path(output).resolve()
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(text, encoding="utf-8")
            print(f"✅ Exported Customer Journey Map JSON to {out_p}")
        else:
            print(text)
    elif fmt == "html":
        out_p = engine.export_html(report, output_path=output)
        print(f"✅ Exported standalone HTML customer journey map to {out_p}")
        print(f"   Journey Coverage: {report.overall_coverage_percentage:.1f}% ({report.addressed_pain_points}/{report.total_pain_points} pain points addressed)")
    else:
        text = engine.format_markdown(report)
        if output:
            out_p = Path(output).resolve()
            out_p.parent.mkdir(parents=True, exist_ok=True)
            out_p.write_text(text, encoding="utf-8")
            print(f"✅ Exported Customer Journey Map report to {out_p}")
        else:
            print(text)
    return 0
