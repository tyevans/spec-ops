"""Domain models and serialization for user personas and discovery reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any
import yaml


@dataclass
class PersonaProfile:
    """Structured representation of a user archetype profile."""

    name: str
    role: str = ""
    role_description: str = ""
    pain_points: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    goals_label: str = "Goals with SpecOps"
    index: int | None = None
    custom_notes: list[str] = field(default_factory=list)

    @property
    def id(self) -> str:
        slug = re.sub(r"[^a-zA-Z0-9]+", "-", self.name.strip().lower()).strip("-")
        return slug.split("-")[0] if slug else "persona"

    def serialize(self, index: int | None = None) -> str:
        idx = index if index is not None else self.index
        prefix = f"## {idx}. " if idx is not None else "## "
        header = f"{prefix}{self.name} — {self.role}" if self.role else f"{prefix}{self.name}"

        lines = [header]
        if self.role_description:
            lines.append(f"- **Role**: {self.role_description}")
        if self.pain_points:
            lines.append("- **Pain Points**:")
            for pp in self.pain_points:
                lines.append(f"  - {pp}")
        if self.goals:
            lines.append(f"- **{self.goals_label}**:")
            for g in self.goals:
                lines.append(f"  - {g}")
        for note in self.custom_notes:
            lines.append(note)

        return "\n".join(lines)


@dataclass
class PersonaDocument:
    """Document model representing PERSONAS.md with frontmatter and markdown sections."""

    frontmatter: dict[str, Any] = field(default_factory=dict)
    raw_frontmatter: str = ""
    preamble: str = (
        "# SpecOps User Personas\n\n"
        "Archetypes representing the software architects, engineering leads, and autonomous AI agents who interact with and rely on SpecOps."
    )
    personas: list[PersonaProfile] = field(default_factory=list)
    postscript: str = ""

    @classmethod
    def parse(cls, content: str) -> PersonaDocument:
        frontmatter: dict[str, Any] = {}
        raw_frontmatter: str = ""
        body = content

        fm_match = re.match(r"^---\n(.*?)\n---\n?", content, re.DOTALL)
        if fm_match:
            raw_frontmatter = fm_match.group(1).strip()
            try:
                frontmatter = yaml.safe_load(raw_frontmatter) or {}
            except Exception:
                frontmatter = {}
            body = content[fm_match.end():]

        parts = re.split(r"(?:\n|^)##\s+", body)
        raw_preamble = parts[0]
        preamble = re.sub(r"\n+---\s*$", "", raw_preamble).strip()

        personas: list[PersonaProfile] = []
        for sec in parts[1:]:
            sec_clean = re.sub(r"\n+---\s*$", "", sec).strip()
            if not sec_clean:
                continue
            lines = sec_clean.splitlines()
            header = lines[0].strip()

            m = re.match(r"^(?:(\d+)\.\s*)?([^\n—–-]+?)(?:\s*[—–-]\s*([^\n]+))?$", header)
            idx = int(m.group(1)) if m and m.group(1) else None
            name = m.group(2).strip() if m else header
            role = m.group(3).strip() if m and m.group(3) else ""

            sec_body = "\n".join(lines[1:]).strip()

            role_m = re.search(r"-\s+\*\*Role\*\*:\s*([^\n]+)", sec_body)
            role_desc = role_m.group(1).strip() if role_m else ""

            pain_m = re.search(r"-\s+\*\*Pain Points\*\*:(.*?)(?=-\s+\*\*|\Z)", sec_body, re.DOTALL)
            pain_points: list[str] = []
            if pain_m:
                for pl in pain_m.group(1).strip().splitlines():
                    pl_s = pl.strip()
                    if pl_s.startswith("-"):
                        pain_points.append(pl_s.lstrip("- ").strip())

            goal_m = re.search(r"-\s+\*\*(Goals[^*]*)\*\*:(.*?)(?=-\s+\*\*|\Z)", sec_body, re.DOTALL)
            goal_label = goal_m.group(1).strip() if goal_m else "Goals with SpecOps"
            goals: list[str] = []
            if goal_m:
                for gl in goal_m.group(2).strip().splitlines():
                    gl_s = gl.strip()
                    if gl_s.startswith("-"):
                        goals.append(gl_s.lstrip("- ").strip())

            custom_notes: list[str] = []
            standard_keys = [r"^-\s+\*\*Role\*\*:", r"^-\s+\*\*Pain Points\*\*:", r"^-\s+\*\*Goals"]
            for bline in lines[1:]:
                if (bline.startswith("- ") or bline.startswith("* ")) and not any(re.match(k, bline) for k in standard_keys):
                    custom_notes.append(bline)

            personas.append(
                PersonaProfile(
                    name=name,
                    role=role,
                    role_description=role_desc,
                    pain_points=pain_points,
                    goals=goals,
                    goals_label=goal_label,
                    index=idx or (len(personas) + 1),
                    custom_notes=custom_notes,
                )
            )

        return cls(
            frontmatter=frontmatter,
            raw_frontmatter=raw_frontmatter,
            preamble=preamble,
            personas=personas,
        )

    def serialize(self) -> str:
        parts: list[str] = []

        if self.raw_frontmatter:
            parts.append(f"---\n{self.raw_frontmatter}\n---\n")
        elif self.frontmatter:
            yaml_str = yaml.dump(self.frontmatter, default_flow_style=False, sort_keys=False)
            parts.append(f"---\n{yaml_str}---\n")

        parts.append(self.preamble.strip())

        rendered_sections: list[str] = []
        for i, persona in enumerate(self.personas, start=1):
            rendered_sections.append(persona.serialize(index=i))

        if rendered_sections:
            parts.append("\n\n---\n\n")
            parts.append("\n\n---\n\n".join(rendered_sections))

        if self.postscript:
            parts.append(f"\n\n{self.postscript.strip()}")

        return "".join(parts) + "\n"


@dataclass
class EmergingArchetype:
    """Discovered persona archetype not yet represented in PERSONAS.md."""

    name: str
    role: str = ""
    sources: list[str] = field(default_factory=list)


@dataclass
class PersonaCoverageStats:
    """Coverage statistics for a single persona profile."""

    id: str
    name: str
    role: str
    prds: list[str] = field(default_factory=list)
    stories: list[str] = field(default_factory=list)
    commits: list[str] = field(default_factory=list)

    @property
    def is_covered(self) -> bool:
        return len(self.stories) > 0 or len(self.prds) > 0

    @property
    def status(self) -> str:
        return "Active" if self.is_covered else "Uncovered"


@dataclass
class PersonaAuditResult:
    """Aggregated audit results across personas, PRDs, stories, and git commits."""

    total_personas: int
    covered_personas: int
    uncovered_personas: list[str]
    coverage_percentage: float
    distribution: dict[str, PersonaCoverageStats]
    emerging_archetypes: list[EmergingArchetype]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_personas": self.total_personas,
            "covered_personas": self.covered_personas,
            "uncovered_personas": self.uncovered_personas,
            "coverage_percentage": round(self.coverage_percentage, 1),
            "distribution": {
                name: {
                    "id": stat.id,
                    "name": stat.name,
                    "role": stat.role,
                    "prds": stat.prds,
                    "stories": stat.stories,
                    "commits": stat.commits,
                    "status": stat.status,
                }
                for name, stat in self.distribution.items()
            },
            "emerging_archetypes": [
                {"name": arch.name, "role": arch.role, "sources": arch.sources}
                for arch in self.emerging_archetypes
            ],
        }

    def format_text(self) -> str:
        lines = [
            "=== SpecOps Persona Discovery & Coverage Audit ===",
            f"Coverage: {self.covered_personas}/{self.total_personas} Personas Active ({self.coverage_percentage:.1f}%)",
            "",
            f"{'Persona':<22} {'Role':<34} {'PRDs':<8} {'Stories':<10} {'Commits':<10} {'Status'}",
            "-" * 96,
        ]
        for name, stat in self.distribution.items():
            short_role = (stat.role[:31] + "...") if len(stat.role) > 34 else stat.role
            lines.append(
                f"{name:<22} {short_role:<34} {len(stat.prds):<8} {len(stat.stories):<10} {len(stat.commits):<10} {stat.status}"
            )

        if self.uncovered_personas:
            lines.append("\n⚠️ Uncovered Personas (0 linked stories or PRDs):")
            for u in self.uncovered_personas:
                lines.append(f"  • {u}")

        if self.emerging_archetypes:
            lines.append("\n🔍 Emerging Archetypes (Unrepresented in PERSONAS.md):")
            for arch in self.emerging_archetypes:
                sources_str = ", ".join(arch.sources)
                lines.append(f"  • {arch.name} ({arch.role}) — Cited in: {sources_str}")
            lines.append("\n💡 Recommendation: Run 'spec-ops persona sync --diff' to preview profile drafts.")
        else:
            lines.append("\n✅ No unrepresented archetypes found. All PRD and story personas are registered.")

        return "\n".join(lines)


@dataclass
class PersonaSyncResult:
    """Result of synthesizing and synchronizing persona additions."""

    emerging_archetypes: list[EmergingArchetype]
    diff: str
    applied: bool
    message: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "emerging_archetypes": [
                {"name": a.name, "role": a.role, "sources": a.sources}
                for a in self.emerging_archetypes
            ],
            "diff": self.diff,
            "applied": self.applied,
            "message": self.message,
        }
