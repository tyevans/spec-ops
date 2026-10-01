"""Autonomous Persona Discovery and Living Maintenance Engine."""

from __future__ import annotations

import difflib
from pathlib import Path
import re
from typing import Any
import yaml

from .git_metadata import GitMetadataHarvester
from .persona_models import (
    EmergingArchetype,
    PersonaAuditResult,
    PersonaCoverageStats,
    PersonaDocument,
    PersonaProfile,
    PersonaSyncResult,
)


class PersonaEngine:
    """Audits persona coverage and synthesizes living additions for emerging archetypes."""

    def __init__(self, root_dir: Path | str) -> None:
        self.root_dir = Path(root_dir).resolve()
        candidates = [
            self.root_dir / "docs" / "project" / "user_stories" / "PERSONAS.md",
            self.root_dir / "docs" / "user_stories" / "PERSONAS.md",
        ]
        self.personas_file = next((c for c in candidates if c.is_file()), candidates[0])

    def parse_personas_doc(self) -> PersonaDocument:
        if not self.personas_file.exists():
            return PersonaDocument()
        content = self.personas_file.read_text(encoding="utf-8")
        return PersonaDocument.parse(content)

    @staticmethod
    def extract_persona_mentions(val: str) -> list[tuple[str, str]]:
        if not val or not val.strip():
            return []
        parts = re.split(r"(?:\s+&\s+|\s+and\s+)(?![^(]*\))", val)
        results: list[tuple[str, str]] = []
        for p in parts:
            p_clean = p.strip()
            if not p_clean:
                continue
            m = re.match(r"^([^(—–-]+?)(?:\s*(?:[—–-]|\()\s*([^)]*)\)?)?$", p_clean)
            if m:
                name = m.group(1).strip()
                role = (m.group(2) or "").strip()
                results.append((name, role))
            else:
                results.append((p_clean, ""))
        return results

    def _match_known_persona(
        self, name: str, role: str, doc: PersonaDocument
    ) -> PersonaProfile | None:
        n_low = name.lower()
        r_low = role.lower()
        for p in doc.personas:
            p_name_low = p.name.lower()
            p_id_low = p.id.lower()
            p_role_low = p.role.lower()
            if n_low == p_name_low or n_low == p_id_low or n_low in p_name_low or p_name_low in n_low:
                return p
            if role and r_low and (r_low == p_role_low or r_low in p_role_low):
                return p
        return None

    def audit(
        self,
        prd_dir: Path | None = None,
        stories_dir: Path | None = None,
        check_git: bool = True,
    ) -> PersonaAuditResult:
        doc = self.parse_personas_doc()
        dist: dict[str, PersonaCoverageStats] = {
            p.name: PersonaCoverageStats(id=p.id, name=p.name, role=p.role)
            for p in doc.personas
        }

        emerging_map: dict[str, EmergingArchetype] = {}

        # 1. Inspect PRDs
        p_dir = prd_dir or (self.root_dir / "docs" / "project" / "product")
        if p_dir.is_dir():
            for prd_path in sorted(p_dir.rglob("*.md")):
                content = prd_path.read_text(encoding="utf-8")
                fm_m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                if not fm_m:
                    continue
                try:
                    fm = yaml.safe_load(fm_m.group(1)) or {}
                except Exception:
                    continue
                raw_persona = fm.get("target_persona") or fm.get("persona")
                if not raw_persona:
                    continue
                prd_id = fm.get("id") or prd_path.stem
                canon_prd = f"PRD-{str(prd_id).upper().replace('PRD-', '').zfill(4)}"
                for m_name, m_role in self.extract_persona_mentions(str(raw_persona)):
                    matched = self._match_known_persona(m_name, m_role, doc)
                    if matched:
                        if canon_prd not in dist[matched.name].prds:
                            dist[matched.name].prds.append(canon_prd)
                    else:
                        emerging_map.setdefault(
                            m_name, EmergingArchetype(name=m_name, role=m_role)
                        ).sources.append(canon_prd)

        # 2. Inspect Stories
        s_dir = stories_dir or (self.root_dir / "docs" / "project" / "user_stories")
        if s_dir.is_dir():
            for s_path in sorted(s_dir.rglob("*.md")):
                if s_path.name == "PERSONAS.md":
                    continue
                content = s_path.read_text(encoding="utf-8")
                fm_m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
                if not fm_m:
                    continue
                try:
                    fm = yaml.safe_load(fm_m.group(1)) or {}
                except Exception:
                    continue
                raw_persona = fm.get("persona") or fm.get("target_persona")
                if not raw_persona:
                    continue
                s_id = fm.get("id") or s_path.stem
                canon_story = f"US-{str(s_id).upper().replace('US-', '').zfill(4)}"
                for m_name, m_role in self.extract_persona_mentions(str(raw_persona)):
                    matched = self._match_known_persona(m_name, m_role, doc)
                    if matched:
                        if canon_story not in dist[matched.name].stories:
                            dist[matched.name].stories.append(canon_story)
                    else:
                        emerging_map.setdefault(
                            m_name, EmergingArchetype(name=m_name, role=m_role)
                        ).sources.append(canon_story)

        # 3. Inspect Git Commits
        if check_git:
            harvester = GitMetadataHarvester(self.root_dir)
            git_data = harvester.harvest()
            seen_commits: set[str] = set()
            for task_id, (commits, _) in git_data.items():
                for c in commits:
                    if c.hash in seen_commits:
                        continue
                    seen_commits.add(c.hash)
                    c_persona = (
                        c.trailers.get("SpecOps-Persona")
                        or c.trailers.get("Persona")
                        or c.trailers.get("Target-Persona")
                    )
                    if c_persona:
                        c_ref = f"commit:{c.hash[:7]}"
                        for m_name, m_role in self.extract_persona_mentions(c_persona):
                            matched = self._match_known_persona(m_name, m_role, doc)
                            if matched:
                                if c_ref not in dist[matched.name].commits:
                                    dist[matched.name].commits.append(c_ref)
                            else:
                                emerging_map.setdefault(
                                    m_name, EmergingArchetype(name=m_name, role=m_role)
                                ).sources.append(c_ref)

        total_p = len(dist)
        covered_p = sum(1 for s in dist.values() if s.is_covered)
        uncovered = [s.name for s in dist.values() if not s.is_covered]
        pct = (covered_p / total_p * 100.0) if total_p > 0 else 100.0

        return PersonaAuditResult(
            total_personas=total_p,
            covered_personas=covered_p,
            uncovered_personas=uncovered,
            coverage_percentage=pct,
            distribution=dist,
            emerging_archetypes=list(emerging_map.values()),
        )

    def synthesize_profile(self, archetype: EmergingArchetype, index: int) -> PersonaProfile:
        role = archetype.role or f"The {archetype.name}"
        desc = (
            f"Subject matter specialist and core contributor driving {archetype.name.lower()} capabilities."
        )
        p1 = f"Cognitive overhead and specification drift when {archetype.name} workflows lack dedicated PMaC primitives."
        p2 = "Absence of automated verification guardrails tailored to this stakeholder perspective."
        g1 = f"First-class representation in SpecOps PRDs and executable user stories."
        g2 = "Automated traceability and continuous validation of archetype outcomes."

        return PersonaProfile(
            name=archetype.name,
            role=role,
            role_description=desc,
            pain_points=[p1, p2],
            goals=[g1, g2],
            goals_label="Goals with SpecOps",
            index=index,
        )

    def sync(
        self,
        apply: bool = False,
        prd_dir: Path | None = None,
        stories_dir: Path | None = None,
        check_git: bool = True,
    ) -> PersonaSyncResult:
        audit_res = self.audit(prd_dir=prd_dir, stories_dir=stories_dir, check_git=check_git)
        if not audit_res.emerging_archetypes:
            return PersonaSyncResult(
                emerging_archetypes=[],
                diff="",
                applied=False,
                message="All archetypes are synchronized with PERSONAS.md.",
            )

        doc = self.parse_personas_doc()
        original_text = doc.serialize()

        new_personas = list(doc.personas)
        start_idx = len(new_personas) + 1
        for i, arch in enumerate(audit_res.emerging_archetypes):
            synthesized = self.synthesize_profile(arch, start_idx + i)
            new_personas.append(synthesized)

        updated_doc = PersonaDocument(
            frontmatter=doc.frontmatter,
            raw_frontmatter=doc.raw_frontmatter,
            preamble=doc.preamble,
            personas=new_personas,
            postscript=doc.postscript,
        )
        new_text = updated_doc.serialize()

        diff_lines = list(
            difflib.unified_diff(
                original_text.splitlines(keepends=True),
                new_text.splitlines(keepends=True),
                fromfile="a/docs/project/user_stories/PERSONAS.md",
                tofile="b/docs/project/user_stories/PERSONAS.md",
            )
        )
        diff_str = "".join(diff_lines)

        if apply and self.personas_file.parent.exists():
            self.personas_file.write_text(new_text, encoding="utf-8")

        return PersonaSyncResult(
            emerging_archetypes=audit_res.emerging_archetypes,
            diff=diff_str,
            applied=apply,
            message=(
                f"Successfully synthesized and applied {len(audit_res.emerging_archetypes)} persona(s)"
                if apply
                else f"Previewed {len(audit_res.emerging_archetypes)} synthesized persona(s)"
            ),
        )
