"""BDD Feature Scenario Coverage Matrix and Living Acceptance Dashboard.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0006, ADR-0009; PRD-0003; US-0094, US-0117.
Target Bounded Context: prd. File length strictly under 400 lines.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

from ..core.parser import extract_frontmatter


def normalize_story_id(raw: str) -> str:
    """Normalizes raw story ID into canonical prefix format (e.g. US-0094)."""
    digits = re.search(r"\d+", raw)
    if digits:
        return f"US-{int(digits.group(0)):04d}"
    clean = re.sub(r"[^A-Za-z0-9_-]", "", raw).strip().upper()
    return clean if clean.startswith("US-") else f"US-{clean or 'STORY'}"


def _slugify(text: str) -> str:
    """Creates a normalized comparison slug from scenario or test names."""
    cleaned = re.sub(r"[^a-zA-Z0-9\s_]", "", text.lower())
    return re.sub(r"[\s_]+", "_", cleaned).strip("_")


@dataclass
class BDDScenarioItem:
    """Coverage status and test binding for a single Gherkin acceptance scenario."""

    story_id: str
    story_title: str
    scenario_title: str
    is_covered: bool
    test_binding: str | None
    target_bc: str

    def to_dict(self) -> dict[str, Any]:
        """Serializes scenario item to a dictionary."""
        return {
            "story_id": self.story_id,
            "story_title": self.story_title,
            "scenario_title": self.scenario_title,
            "is_covered": self.is_covered,
            "test_binding": self.test_binding,
            "target_bc": self.target_bc,
        }


@dataclass
class StoryCoverageReport:
    """Aggregated BDD scenario coverage report for a user story."""

    story_id: str
    story_title: str
    target_bc: str
    total_scenarios: int
    covered_scenarios: int
    coverage_pct: float
    scenarios: list[BDDScenarioItem] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializes story coverage report to a dictionary."""
        return {
            "story_id": self.story_id,
            "story_title": self.story_title,
            "target_bc": self.target_bc,
            "total_scenarios": self.total_scenarios,
            "covered_scenarios": self.covered_scenarios,
            "coverage_pct": self.coverage_pct,
            "scenarios": [s.to_dict() for s in self.scenarios],
        }


@dataclass
class BDDCoverageMatrix:
    """Repository-wide BDD scenario coverage matrix and living acceptance dashboard."""

    stories: list[StoryCoverageReport]
    total_stories: int
    total_scenarios: int
    covered_scenarios: int
    overall_coverage_pct: float

    def to_dict(self) -> dict[str, Any]:
        """Serializes coverage matrix to a dictionary."""
        return {
            "total_stories": self.total_stories,
            "total_scenarios": self.total_scenarios,
            "covered_scenarios": self.covered_scenarios,
            "overall_coverage_pct": self.overall_coverage_pct,
            "stories": [s.to_dict() for s in self.stories],
        }

    def summary(self) -> str:
        """Formats living acceptance dashboard and scenario coverage summary."""
        lines = [
            "=== SpecOps BDD Scenario Coverage Matrix ===",
            f"Total User Stories: {self.total_stories}",
            f"Total Scenarios: {self.total_scenarios}",
            f"Covered Scenarios: {self.covered_scenarios} ({self.overall_coverage_pct:.1f}%)",
            "",
            "Coverage by User Story:",
        ]

        for s in self.stories:
            icon = "✅" if s.covered_scenarios == s.total_scenarios and s.total_scenarios > 0 else (
                "⚠️" if s.total_scenarios > 0 else "ℹ️"
            )
            lines.append(
                f"  {icon} [{s.story_id}] {s.story_title} "
                f"({s.covered_scenarios}/{s.total_scenarios} covered, {s.coverage_pct:.1f}%) [BC: {s.target_bc}]"
            )
            for sc in s.scenarios:
                if sc.is_covered:
                    lines.append(f"     - [x] {sc.scenario_title} -> {sc.test_binding}")
                else:
                    lines.append(f"     - [ ] {sc.scenario_title} (missing test binding)")

        missing_items = [
            (s.story_id, sc.scenario_title)
            for s in self.stories
            for sc in s.scenarios
            if not sc.is_covered
        ]
        if missing_items:
            lines.append("")
            lines.append(f"⚠️  Missing Scenario Bindings ({len(missing_items)}):")
            for sid, stitle in missing_items:
                lines.append(f"   • [{sid}] {stitle}")

        return "\n".join(lines)


class BDDCoverageAuditor:
    """Audits accepted user stories against pytest-bdd test suites to build coverage matrix."""

    def __init__(self, root_dir: Path | None = None) -> None:
        self.root_dir = root_dir

    @classmethod
    def extract_scenarios_from_content(cls, content: str) -> list[str]:
        """Extracts deterministic list of Gherkin scenario titles from Markdown or Gherkin text."""
        raw_titles = re.findall(
            r"^\s*(?:Scenario|Scenario Outline):\s*(.+)$", content, re.MULTILINE
        )
        if not raw_titles:
            raw_titles = re.findall(
                r"^\s*#{2,4}\s*Scenario(?:\s+\d+)?:?\s*(.+)$", content, re.MULTILINE
            )

        scenarios: list[str] = []
        for t in raw_titles:
            clean = t.strip().rstrip(":").strip()
            if clean and clean not in scenarios:
                scenarios.append(clean)
        return scenarios

    @classmethod
    def _determine_target_bc(cls, meta: dict[str, Any], stories_dir: Path) -> str:
        """Resolves target bounded context from frontmatter, PRDs, or feature conventions."""
        explicit_bc = str(meta.get("target_bc") or meta.get("bc") or meta.get("component") or "").strip()
        if explicit_bc:
            return explicit_bc

        feat = str(meta.get("feature") or "").upper()
        feature_map = {
            "CORE": "core",
            "HLT": "health",
            "HLN": "health",
            "PRD": "prd",
            "SEC": "security",
            "VIS": "visualizer",
            "WORK": "worker",
            "REL": "release",
            "VCS": "vcs",
            "SND": "sandbox",
            "GTE": "gate",
            "SCH": "schema",
            "MAP": "export",
            "CLI": "cli",
            "SCAF": "scaffold",
            "DFT": "drift",
            "AGT": "agent",
        }
        for prefix, mapped_bc in feature_map.items():
            if f"-{prefix}-" in feat or feat.startswith(f"FEAT-{prefix}"):
                return mapped_bc

        gov_prd = str(meta.get("governing_prd") or "").strip()
        if gov_prd:
            digits = re.search(r"\d+", gov_prd)
            prd_num = digits.group(0) if digits else ""
            prd_candidates = [
                stories_dir.parent.parent / "product" / "accepted",
                stories_dir.parent.parent / "product",
            ]
            for prd_dir in prd_candidates:
                if prd_dir.exists():
                    for p in prd_dir.glob("*.md"):
                        p_lower = p.name.lower()
                        if gov_prd.lower() in p_lower or (prd_num and prd_num in p_lower):
                            pmeta, _ = extract_frontmatter(p.read_text(encoding="utf-8"))
                            pbc = pmeta.get("component") or pmeta.get("target_bc")
                            if pbc:
                                return str(pbc).strip()

        return "core"

    @classmethod
    def _scan_tests(
        cls, tests_dir: Path
    ) -> tuple[
        dict[str, list[str]],
        dict[str, list[str]],
        dict[str, str],
        dict[str, str],
    ]:
        """Scans test directory for feature files, scenarios(...) bindings, and test functions."""
        feature_to_scenarios: dict[str, list[str]] = {}
        test_to_features: dict[str, list[str]] = {}
        scenario_decorators: dict[str, str] = {}
        func_to_test: dict[str, str] = {}

        if not tests_dir.exists():
            return feature_to_scenarios, test_to_features, scenario_decorators, func_to_test

        for feat_path in tests_dir.glob("**/*.feature"):
            try:
                feat_content = feat_path.read_text(encoding="utf-8")
                scs = cls.extract_scenarios_from_content(feat_content)
                feature_to_scenarios[feat_path.name] = scs
            except Exception:
                continue

        for tf in tests_dir.glob("**/test_*.py"):
            try:
                text = tf.read_text(encoding="utf-8")
            except Exception:
                continue

            for m in re.finditer(r"scenarios\((.*?)\)", text, re.DOTALL):
                args_text = m.group(1)
                for f in re.findall(r"[\"'](?:.*?/)?([a-zA-Z0-9_\-\.]+\.feature)[\"']", args_text):
                    test_to_features.setdefault(f, []).append(tf.name)

            for m in re.finditer(
                r"@scenario\([\"'](?:.*?/)?([a-zA-Z0-9_\-\.]+\.feature)[\"'],\s*[\"'](.+?)[\"']\)\s*(?:async\s+)?def\s+([a-zA-Z0-9_]+)",
                text,
            ):
                sc_title, fn_name = m.group(2).strip(), m.group(3)
                scenario_decorators[sc_title.lower()] = f"{tf.name}::{fn_name}"

            for m in re.finditer(r"def\s+(test_[a-zA-Z0-9_]+)\s*\(", text):
                fn = m.group(1)
                slug = _slugify(fn)
                func_to_test[slug] = f"{tf.name}::{fn}"

        return feature_to_scenarios, test_to_features, scenario_decorators, func_to_test

    @classmethod
    def audit(
        cls,
        stories_dir: Path,
        tests_dir: Path,
        target_bc: str | None = None,
    ) -> BDDCoverageMatrix:
        """Audits all accepted user stories and produces a BDD scenario coverage matrix."""
        if not stories_dir.exists():
            return BDDCoverageMatrix(
                stories=[],
                total_stories=0,
                total_scenarios=0,
                covered_scenarios=0,
                overall_coverage_pct=100.0,
            )

        feat_scenarios, test_features, decorators, func_tests = cls._scan_tests(tests_dir)

        story_reports: list[StoryCoverageReport] = []
        md_files = sorted(stories_dir.glob("*.md"))

        for story_file in md_files:
            try:
                raw_text = story_file.read_text(encoding="utf-8")
            except Exception:
                continue

            meta, _ = extract_frontmatter(raw_text)
            story_id = normalize_story_id(str(meta.get("id", story_file.stem)))
            story_title = str(meta.get("title", story_file.stem)).strip()
            story_bc = cls._determine_target_bc(meta, stories_dir)

            if target_bc and target_bc.strip().lower() != story_bc.lower():
                continue

            scenario_titles = cls.extract_scenarios_from_content(raw_text)
            scenario_items: list[BDDScenarioItem] = []

            for sc_title in scenario_titles:
                sc_lower = sc_title.lower()
                sc_slug = _slugify(sc_title)
                is_cov = False
                binding: str | None = None

                if sc_lower in decorators:
                    is_cov = True
                    binding = decorators[sc_lower]
                else:
                    for feat_name, sc_list in feat_scenarios.items():
                        if any(item.lower() == sc_lower for item in sc_list):
                            if feat_name in test_features:
                                is_cov = True
                                binding = test_features[feat_name][0]
                                break

                if not is_cov:
                    for func_slug, target_binding in func_tests.items():
                        if sc_slug in func_slug or func_slug in sc_slug:
                            is_cov = True
                            binding = target_binding
                            break

                scenario_items.append(
                    BDDScenarioItem(
                        story_id=story_id,
                        story_title=story_title,
                        scenario_title=sc_title,
                        is_covered=is_cov,
                        test_binding=binding,
                        target_bc=story_bc,
                    )
                )

            total_sc = len(scenario_items)
            cov_sc = sum(1 for item in scenario_items if item.is_covered)
            cov_pct = round((cov_sc / total_sc) * 100.0, 1) if total_sc > 0 else 100.0

            story_reports.append(
                StoryCoverageReport(
                    story_id=story_id,
                    story_title=story_title,
                    target_bc=story_bc,
                    total_scenarios=total_sc,
                    covered_scenarios=cov_sc,
                    coverage_pct=cov_pct,
                    scenarios=scenario_items,
                )
            )

        total_stories = len(story_reports)
        total_scenarios = sum(s.total_scenarios for s in story_reports)
        covered_scenarios = sum(s.covered_scenarios for s in story_reports)
        overall_pct = (
            round((covered_scenarios / total_scenarios) * 100.0, 1)
            if total_scenarios > 0
            else 100.0
        )

        return BDDCoverageMatrix(
            stories=story_reports,
            total_stories=total_stories,
            total_scenarios=total_scenarios,
            covered_scenarios=covered_scenarios,
            overall_coverage_pct=overall_pct,
        )
