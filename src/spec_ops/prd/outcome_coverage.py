"""Domain model and state handlers for PRD checkable outcome to BDD scenario coverage auditing."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.parser import extract_frontmatter
from .delta import CheckableOutcome, parse_checkable_outcomes


def _clean_prd_id(raw_id: str) -> str:
    """Normalizes raw PRD id into canonical format (e.g. PRD-0003)."""
    digits = re.search(r"\d+", raw_id)
    if digits:
        return f"PRD-{int(digits.group(0)):04d}"
    clean = re.sub(r"[^A-Za-z0-9_-]", "", raw_id).strip().upper()
    return clean if clean.startswith("PRD-") else f"PRD-{clean or 'UNKNOWN'}"


def _clean_story_id(raw_id: str) -> str:
    """Normalizes raw story id into canonical format (e.g. US-0120)."""
    digits = re.search(r"\d+", raw_id)
    if digits:
        return f"US-{int(digits.group(0)):04d}"
    clean = re.sub(r"[^A-Za-z0-9_-]", "", raw_id).strip().upper()
    return clean if clean.startswith("US-") else f"US-{clean or 'UNKNOWN'}"


def _slugify(text: str) -> str:
    """Creates a normalized comparison slug from text."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s_]", "", text.lower())
    return re.sub(r"[\s_]+", "_", cleaned).strip("_")


@dataclass
class OutcomeScenarioItem:
    """Coverage status and test bindings for a single PRD checkable outcome."""

    outcome_id: int
    outcome_text: str
    linked_stories: list[str] = field(default_factory=list)
    linked_scenarios: list[str] = field(default_factory=list)
    test_bindings: list[str] = field(default_factory=list)
    is_covered: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Serializes outcome item to dictionary."""
        return asdict(self)


@dataclass
class PRDTestCoverageReport:
    """Aggregated test coverage metrics across checkable outcomes and linked BDD scenarios."""

    prd_id: str
    prd_title: str
    stage: str
    total_outcomes: int = 0
    covered_outcomes: int = 0
    outcome_coverage_pct: float = 100.0
    total_bdd_scenarios: int = 0
    covered_bdd_scenarios: int = 0
    scenario_coverage_pct: float = 100.0
    outcome_items: list[OutcomeScenarioItem] = field(default_factory=list)

    @property
    def is_fully_covered(self) -> bool:
        """Returns True if all checkable outcomes are covered by executable tests."""
        return self.total_outcomes > 0 and self.covered_outcomes >= self.total_outcomes

    def to_dict(self) -> dict[str, Any]:
        """Serializes report to dictionary."""
        return {
            "prd_id": self.prd_id,
            "prd_title": self.prd_title,
            "stage": self.stage,
            "total_outcomes": self.total_outcomes,
            "covered_outcomes": self.covered_outcomes,
            "outcome_coverage_pct": self.outcome_coverage_pct,
            "total_bdd_scenarios": self.total_bdd_scenarios,
            "covered_bdd_scenarios": self.covered_bdd_scenarios,
            "scenario_coverage_pct": self.scenario_coverage_pct,
            "is_fully_covered": self.is_fully_covered,
            "outcome_items": [item.to_dict() for item in self.outcome_items],
        }

    def summary(self) -> str:
        """Formats a human-readable summary of the PRD outcome coverage report."""
        status_icon = "✅" if self.is_fully_covered else "⚠️"
        lines = [
            f"=== {status_icon} PRD Outcome & BDD Scenario Test Coverage: {self.prd_id} ===",
            f"Title: {self.prd_title} (Stage: {self.stage})",
            f"Checkable Outcomes: {self.covered_outcomes}/{self.total_outcomes} ({self.outcome_coverage_pct:.1f}%)",
            f"BDD Scenarios: {self.covered_bdd_scenarios}/{self.total_bdd_scenarios} ({self.scenario_coverage_pct:.1f}%)",
            "",
            "Outcome Breakdown:",
        ]
        for item in self.outcome_items:
            cov_mark = "✅" if item.is_covered else "❌"
            stories = ", ".join(item.linked_stories) or "None"
            scenarios_cnt = len(item.linked_scenarios)
            tests_cnt = len(item.test_bindings)
            lines.append(
                f"  [{cov_mark}] Outcome {item.outcome_id}: {item.outcome_text}\n"
                f"      Linked Stories: {stories} | Scenarios: {scenarios_cnt} | Test Bindings: {tests_cnt}"
            )
        return "\n".join(lines)


class PRDOutcomeCoverageEngine:
    """Domain engine that correlates PRD outcomes with BDD acceptance scenarios and test step files."""

    def __init__(
        self,
        repo_root: Path | str | None = None,
        config: SpecOpsConfig | None = None,
    ) -> None:
        self.root = Path(repo_root or (config.root_dir if config else Path.cwd())).resolve()

    def audit_prd(self, prd_id_or_path: str) -> PRDTestCoverageReport:
        """Computes test coverage across checkable outcomes and linked BDD scenarios for target PRD."""
        prd_file = self._resolve_prd_file(prd_id_or_path)
        if not prd_file or not prd_file.exists():
            return PRDTestCoverageReport(
                prd_id=_clean_prd_id(prd_id_or_path),
                prd_title="Not Found",
                stage="unknown",
                total_outcomes=0,
                covered_outcomes=0,
                outcome_coverage_pct=0.0,
                total_bdd_scenarios=0,
                covered_bdd_scenarios=0,
                scenario_coverage_pct=0.0,
            )

        content = prd_file.read_text(encoding="utf-8")
        meta, _ = extract_frontmatter(content)
        prd_id = _clean_prd_id(str(meta.get("id") or prd_file.stem))
        prd_title = str(meta.get("title") or prd_file.stem)
        stage = prd_file.parent.name.lower()

        outcomes = parse_checkable_outcomes(content)
        stories_map = self._collect_stories_for_prd(prd_id)
        test_bindings_map = self._collect_test_bindings()

        outcome_items: list[OutcomeScenarioItem] = []
        all_linked_scenarios: set[str] = set()
        all_covered_scenarios: set[str] = set()

        for outcome in outcomes:
            linked_stories: list[str] = []
            linked_scenarios: list[str] = []
            test_bindings: list[str] = []

            for s_id, s_data in stories_map.items():
                s_outcome = s_data.get("outcome_id")
                # Direct outcome_id match or text similarity
                is_match = False
                if s_outcome is not None and str(s_outcome) == str(outcome.id):
                    is_match = True
                elif _slugify(outcome.clean_text) in _slugify(s_data.get("title", "")):
                    is_match = True

                if is_match:
                    linked_stories.append(s_id)
                    scenarios = s_data.get("scenarios", [])
                    linked_scenarios.extend(scenarios)
                    for sc in scenarios:
                        all_linked_scenarios.add(sc)
                        bindings = test_bindings_map.get(s_id, [])
                        if bindings:
                            all_covered_scenarios.add(sc)
                            test_bindings.extend(bindings)

            is_covered = len(test_bindings) > 0 and len(linked_scenarios) > 0
            outcome_items.append(
                OutcomeScenarioItem(
                    outcome_id=outcome.id,
                    outcome_text=outcome.clean_text,
                    linked_stories=sorted(list(set(linked_stories))),
                    linked_scenarios=sorted(list(set(linked_scenarios))),
                    test_bindings=sorted(list(set(test_bindings))),
                    is_covered=is_covered,
                )
            )

        total_outcomes = len(outcome_items)
        covered_outcomes = sum(1 for item in outcome_items if item.is_covered)
        outcome_pct = (
            round((covered_outcomes / total_outcomes) * 100.0, 1)
            if total_outcomes > 0
            else 100.0
        )

        total_scenarios = len(all_linked_scenarios)
        covered_scenarios = len(all_covered_scenarios)
        scenario_pct = (
            round((covered_scenarios / total_scenarios) * 100.0, 1)
            if total_scenarios > 0
            else 100.0
        )

        return PRDTestCoverageReport(
            prd_id=prd_id,
            prd_title=prd_title,
            stage=stage,
            total_outcomes=total_outcomes,
            covered_outcomes=covered_outcomes,
            outcome_coverage_pct=outcome_pct,
            total_bdd_scenarios=total_scenarios,
            covered_bdd_scenarios=covered_scenarios,
            scenario_coverage_pct=scenario_pct,
            outcome_items=outcome_items,
        )

    def audit_all(self, stage_filter: str | None = None) -> list[PRDTestCoverageReport]:
        """Audits all PRD documents across project lifecycle stages."""
        prd_dir = self.root / "docs" / "project" / "product"
        if not prd_dir.exists():
            return []

        reports: list[PRDTestCoverageReport] = []
        stages = [stage_filter.lower()] if stage_filter else ["accepted", "shaped", "idea", "shipped"]

        for s in stages:
            s_dir = prd_dir / s
            if not s_dir.exists():
                continue
            for f in sorted(s_dir.glob("*.md")):
                if f.name == "REGISTRY.md":
                    continue
                reports.append(self.audit_prd(str(f)))

        return reports

    def _resolve_prd_file(self, prd_id_or_path: str) -> Path | None:
        cand = Path(prd_id_or_path)
        if cand.is_file():
            return cand
        cand_root = self.root / prd_id_or_path
        if cand_root.is_file():
            return cand_root

        clean_id = _clean_prd_id(prd_id_or_path).lower()
        prd_dir = self.root / "docs" / "project" / "product"
        if prd_dir.exists():
            for f in prd_dir.rglob("*.md"):
                if f.name == "REGISTRY.md":
                    continue
                if clean_id in f.stem.lower() or prd_id_or_path.lower() in f.stem.lower():
                    return f
        return None

    def _collect_stories_for_prd(self, prd_id: str) -> dict[str, dict[str, Any]]:
        stories_dir = self.root / "docs" / "project" / "user_stories"
        if not stories_dir.exists():
            return {}

        matching_stories: dict[str, dict[str, Any]] = {}
        for f in stories_dir.rglob("*.md"):
            if f.name in ("REGISTRY.md", "PERSONAS.md"):
                continue
            try:
                txt = f.read_text(encoding="utf-8")
                meta, body = extract_frontmatter(txt)
                gov_prd = str(meta.get("governing_prd") or "")
                if _clean_prd_id(gov_prd) != prd_id and prd_id.lower() not in f.read_text().lower():
                    continue

                s_id = _clean_story_id(str(meta.get("id") or f.stem))
                scenarios: list[str] = []
                for line in body.splitlines():
                    m = re.match(r"^\s*Scenario:\s*(.+)$", line)
                    if m:
                        scenarios.append(m.group(1).strip())

                matching_stories[s_id] = {
                    "title": str(meta.get("title") or f.stem),
                    "outcome_id": meta.get("outcome_id"),
                    "scenarios": scenarios,
                    "file_path": f,
                }
            except Exception:
                continue

        return matching_stories

    def _collect_test_bindings(self) -> dict[str, list[str]]:
        tests_dir = self.root / "tests"
        if not tests_dir.exists():
            return {}

        bindings: dict[str, list[str]] = {}
        for f in tests_dir.rglob("test_bdd_*.py"):
            try:
                content = f.read_text(encoding="utf-8")
                search_space = f"{f.name} {content}".lower()
                for m in re.finditer(r"us[-_]?0*(\d+)", search_space):
                    s_id = f"US-{int(m.group(1)):04d}"
                    bindings.setdefault(s_id, []).append(f.name)
            except Exception:
                continue

        return bindings
