"""Definition of Ready (DoR) and Definition of Done (DoD) lifecycle gates for autonomous orchestration."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .models import Task
from .parser import extract_frontmatter

# Canonical Definition of Ready (DoR) Gate Rule Keys
DOR_RULE_METADATA = "Task Metadata Complete"
DOR_RULE_ARTIFACTS = "Governing Artifacts Linked"
DOR_RULE_BDD_SPEC = "Executable BDD Specification"
DOR_RULE_PROPERTIES = "Generative Property Invariants Identified"
DOR_RULE_MUTATION = "Mutation Testing Scope Defined"
DOR_RULE_INVEST = "INVEST Criteria Satisfied"
DOR_RULE_DOCS = "Documentation Review"

ALL_DOR_GATE_RULES: list[str] = [
    DOR_RULE_METADATA,
    DOR_RULE_ARTIFACTS,
    DOR_RULE_BDD_SPEC,
    DOR_RULE_PROPERTIES,
    DOR_RULE_MUTATION,
    DOR_RULE_INVEST,
    DOR_RULE_DOCS,
]

# Canonical Definition of Done (DoD) Gate Rule Keys
DOD_RULE_FRONTDOOR = "Blackbox Frontdoor Verification"
DOD_RULE_BDD_PASS = "Executable BDD Scenarios Passing"
DOD_RULE_HYPOTHESIS = "Hypothesis Property Tests Passing"
DOD_RULE_MUTATION_KILL = "Mutmut Mutation Score Attained"
DOD_RULE_HEALTH = "Codebase Health Check"
DOD_RULE_LOCKFILE = "Lockfile Integrity"
DOD_RULE_DOCS_SYNC = "Documentation Integrity (Diataxis)"
DOD_RULE_BACKLOG_SYNC = "Strict Backlog Progression"
DOD_RULE_COMMIT_PROVENANCE = "Commit Provenance Trailers"
DOD_RULE_DUAL_CUSTODY = "Dual-Custody Human Sign-Off"

ALL_DOD_GATE_RULES: list[str] = [
    DOD_RULE_FRONTDOOR,
    DOD_RULE_BDD_PASS,
    DOD_RULE_HYPOTHESIS,
    DOD_RULE_MUTATION_KILL,
    DOD_RULE_HEALTH,
    DOD_RULE_LOCKFILE,
    DOD_RULE_DOCS_SYNC,
    DOD_RULE_BACKLOG_SYNC,
    DOD_RULE_COMMIT_PROVENANCE,
    DOD_RULE_DUAL_CUSTODY,
]


@dataclass
class DoRGateResult:
    """Evaluation result for Definition of Ready (DoR) gate checks."""

    task_id: str
    passed: bool
    rules: dict[str, bool] = field(default_factory=dict)
    violations: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DoDGateResult:
    """Evaluation result for Definition of Done (DoD) gate checks."""

    task_id: str
    passed: bool
    rules: dict[str, bool] = field(default_factory=dict)
    violations: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LifecycleGateOrchestrator:
    """Evaluates and enforces Definition of Ready (DoR) and Definition of Done (DoD) gates."""

    @classmethod
    def evaluate_dor(cls, task: Task, repo_root: Path | None = None) -> DoRGateResult:
        """Audits a task against all 7 canonical Definition of Ready (DoR) criteria."""
        rules: dict[str, bool] = {r: False for r in ALL_DOR_GATE_RULES}
        violations: list[str] = []
        recommendations: list[str] = []

        # 1. Task Metadata Complete
        metadata_ok = bool(task.id and task.title and task.target_bc and (task.status or "Refined"))
        rules[DOR_RULE_METADATA] = metadata_ok
        if not metadata_ok:
            violations.append("Missing required frontmatter metadata: id, title, target_bc, or status.")

        # 2. Governing Artifacts Linked
        has_artifacts = bool(task.governing_prds and task.governing_stories and task.governing_adrs)
        rules[DOR_RULE_ARTIFACTS] = has_artifacts
        if not has_artifacts:
            violations.append("Task must cite governing PRDs, user stories, and ADRs in frontmatter.")

        # Inspect task markdown body if available
        body = ""
        if task.file_path and Path(task.file_path).exists():
            try:
                content = Path(task.file_path).read_text(encoding="utf-8", errors="replace")
                _, body = extract_frontmatter(content)
            except Exception:
                pass

        # 3. Executable BDD Specification
        has_bdd = "scenario:" in body.lower() or "given " in body.lower()
        rules[DOR_RULE_BDD_SPEC] = has_bdd
        if not has_bdd:
            violations.append("Task specification must provide executable Gherkin scenarios (Given ... When ... Then).")

        # 4. Generative Property Invariants Identified
        has_props = "@given" in body.lower() or "hypothesis" in body.lower() or "property invariant" in body.lower()
        rules[DOR_RULE_PROPERTIES] = has_props
        if not has_props:
            violations.append("Task must define generative property invariants (@given) for Hypothesis verification.")

        # 5. Mutation Testing Scope Defined
        has_mut = "mutmut" in body.lower() or "mutation" in body.lower() or "kill score" in body.lower()
        rules[DOR_RULE_MUTATION] = has_mut
        if not has_mut:
            violations.append("Task must identify target modules and >=80% mutant kill score under Mutmut.")

        # 6. INVEST Criteria Satisfied
        invest_ok = "<500 lines" in body.lower() or "invest" in body.lower() or len(body.splitlines()) < 400
        rules[DOR_RULE_INVEST] = invest_ok
        if not invest_ok:
            violations.append("Task slice must satisfy INVEST criteria with touched files strictly <500 lines.")

        # 7. Documentation Review
        docs_ok = "docs" in body.lower() or "diataxis" in body.lower() or "documentation" in body.lower()
        rules[DOR_RULE_DOCS] = docs_ok
        if not docs_ok:
            recommendations.append("Review relevant existing documentation in docs/ to prevent convention divergence.")

        passed = all(rules.values())
        return DoRGateResult(
            task_id=task.canonical_id,
            passed=passed,
            rules=rules,
            violations=violations,
            recommendations=recommendations,
        )

    @classmethod
    def evaluate_dod(
        cls,
        task: Task,
        verification_data: dict[str, Any] | None = None,
    ) -> DoDGateResult:
        """Audits completed task implementation against all 10 canonical Definition of Done (DoD) criteria."""
        data = verification_data or {}
        rules: dict[str, bool] = {r: False for r in ALL_DOD_GATE_RULES}
        violations: list[str] = []
        recommendations: list[str] = []

        # 1. Blackbox Frontdoor Verification
        frontdoors = bool(data.get("frontdoors_passed", False))
        rules[DOD_RULE_FRONTDOOR] = frontdoors
        if not frontdoors:
            violations.append("100% test pass rate required verifying observable contracts without private mocks (ADR-0003).")

        # 2. Executable BDD Scenarios Passing
        bdd_ok = bool(data.get("bdd_passed", False))
        rules[DOD_RULE_BDD_PASS] = bdd_ok
        if not bdd_ok:
            violations.append("All Gherkin acceptance criteria executed via pytest-bdd must pass cleanly (ADR-0006).")

        # 3. Hypothesis Property Tests Passing
        hypo_ok = bool(data.get("hypothesis_passed", False))
        rules[DOD_RULE_HYPOTHESIS] = hypo_ok
        if not hypo_ok:
            violations.append("Generative property tests must verify invariants without shrinking failures (ADR-0009).")

        # 4. Mutmut Mutation Score Attained
        mut_score = float(data.get("mutation_score", 0.0))
        mut_ok = mut_score >= 80.0
        rules[DOD_RULE_MUTATION_KILL] = mut_ok
        if not mut_ok:
            violations.append(f"Mutant kill score must reach >=80% under Mutmut (actual: {mut_score:.1f}%).")

        # 5. Codebase Health Check
        health_ok = bool(data.get("health_passed", False))
        rules[DOD_RULE_HEALTH] = health_ok
        if not health_ok:
            violations.append("spec-ops health must report 0 file limit violations (<500 lines) and PRIORITY.md sync.")

        # 6. Lockfile Integrity
        lock_ok = bool(data.get("lockfile_intact", True))
        rules[DOD_RULE_LOCKFILE] = lock_ok
        if not lock_ok:
            violations.append("uv lock --check must pass cleanly without unstaged dependency drift.")

        # 7. Documentation Integrity (Diataxis)
        docs_ok = bool(data.get("docs_synced", False))
        rules[DOD_RULE_DOCS_SYNC] = docs_ok
        if not docs_ok:
            violations.append("Documentation in docs/ must be updated to reflect public contract changes.")

        # 8. Strict Backlog Progression
        backlog_ok = bool(data.get("backlog_progressed", False))
        rules[DOD_RULE_BACKLOG_SYNC] = backlog_ok
        if not backlog_ok:
            violations.append("Task must transition from refined/ to complete/ and atomically sync PRIORITY.md (ADR-0005).")

        # 9. Commit Provenance Trailers
        trailers_ok = bool(data.get("commit_trailers_valid", False))
        rules[DOD_RULE_COMMIT_PROVENANCE] = trailers_ok
        if not trailers_ok:
            violations.append("Commits must include structured RFC 822 trailers (SpecOps-Task: TASK-XXXX).")

        # 10. Dual-Custody Human Sign-Off
        sign_ok = bool(data.get("dual_custody_signed", False))
        rules[DOD_RULE_DUAL_CUSTODY] = sign_ok
        if not sign_ok:
            violations.append("Task review brief must be signed off by authorized human architect (ADR-0016).")

        passed = all(rules.values())
        return DoDGateResult(
            task_id=task.canonical_id,
            passed=passed,
            rules=rules,
            violations=violations,
            recommendations=recommendations,
        )

    @classmethod
    def format_gate_report(cls, result: DoRGateResult | DoDGateResult) -> str:
        """Renders an ASCII summary table for DoR or DoD audit outcomes."""
        gate_type = "Definition of Ready (DoR)" if isinstance(result, DoRGateResult) else "Definition of Done (DoD)"
        lines = [
            f"=== {gate_type} Gate Audit: {result.task_id} ===",
            f"Status: {'✅ PASSED' if result.passed else '❌ FAILED'}",
            f"{'Rule Check':<42} | Status",
            f"{'-' * 42}-|-------",
        ]
        for rule, ok in result.rules.items():
            lines.append(f"{rule:<42} | {'Pass' if ok else 'Fail'}")

        if result.violations:
            lines.append("\nViolations:")
            for v in result.violations:
                lines.append(f"  ❌ {v}")

        if result.recommendations:
            lines.append("\nRecommendations:")
            for r in result.recommendations:
                lines.append(f"  💡 {r}")

        return "\n".join(lines)
