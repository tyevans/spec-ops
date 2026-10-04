"""Definition of Ready (DoR) gatekeeper and ticket health auditor."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

from ..config.models import SpecOpsConfig
from ..core.models import Task
from ..core.parser import extract_frontmatter

RULE_YAML_FRONTMATTER = "Complete YAML frontmatter"
RULE_PERSONA_PRD = "Linked Persona & PRD"
RULE_GOVERNING_ADRS = "Cited Governing ADRs"
RULE_GHERKIN_SCENARIOS = "Executable Gherkin Scenarios"
RULE_BOUNDED_CONTEXT = "Defined Target Bounded Context"
RULE_FILE_LIMIT_SCOPE = "Feasible File Limit Scope"
RULE_MUTATION_SCOPE = "Mutation Testing Scope Defined"

ALL_DOR_RULES: list[str] = [
    RULE_YAML_FRONTMATTER,
    RULE_PERSONA_PRD,
    RULE_GOVERNING_ADRS,
    RULE_GHERKIN_SCENARIOS,
    RULE_BOUNDED_CONTEXT,
    RULE_FILE_LIMIT_SCOPE,
    RULE_MUTATION_SCOPE,
]

KNOWN_PERSONAS = {
    "alex",
    "jordan",
    "morgan",
    "riley",
    "taylor",
    "developer",
    "architect",
    "user",
}


@dataclass
class DoRAuditReport:
    """Report detailing Definition of Ready (DoR) audit outcomes."""

    task_id: str
    is_ready: bool
    rules: dict[str, bool] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def format_report(self) -> str:
        """Renders a human-readable table of DoR rule checks."""
        lines = [f"=== Definition of Ready (DoR) Audit: {self.task_id} ==="]
        lines.append(f"{'Rule Check':<34} | Status")
        lines.append(f"{'-' * 34}-|-------")
        for rule in ALL_DOR_RULES:
            status = "Pass" if self.rules.get(rule, False) else "Fail"
            lines.append(f"{rule:<34} | {status}")
        if self.errors:
            lines.append("\nViolations:")
            for err in self.errors:
                lines.append(f"  ❌ {err}")
        if self.recommendations:
            lines.append("\nRecommendations:")
            for rec in self.recommendations:
                lines.append(f"  💡 {rec}")
        return "\n".join(lines)


def _get(task: Task | dict[str, Any], field_name: str) -> Any:
    if isinstance(task, Task):
        return getattr(task, field_name, None)
    return task.get(field_name)


def _get_task_id(task: Task | dict[str, Any]) -> str:
    if isinstance(task, Task):
        return task.canonical_id
    raw = str(task.get("id", ""))
    clean = raw.upper().replace("TASK-", "").replace("SPIKE-", "").lstrip("0")
    prefix = "SPIKE-" if raw.upper().startswith("SPIKE") else "TASK-"
    return f"{prefix}{clean.zfill(4)}" if clean else (raw or "TASK-UNKNOWN")


def _get_task_text(task: Task | dict[str, Any]) -> str:
    if isinstance(task, Task):
        raw_md = task.raw_markdown or ""
        body = task.body or ""
        file_text = ""
        if task.file_path and task.file_path.is_file():
            try:
                file_text = task.file_path.read_text(encoding="utf-8")
            except OSError:
                file_text = ""
        return f"{raw_md}\n{body}\n{file_text}"
    return str(
        task.get("body", "")
        or task.get("raw_markdown", "")
        or task.get("text", "")
        or task.get("content", "")
        or ""
    )


def audit_task_health(
    task: Task | dict[str, Any], config: SpecOpsConfig, strict: bool = False
) -> DoRAuditReport:
    """Evaluates whether a backlog task satisfies all 7 Definition of Ready (DoR) criteria."""
    task_id = _get_task_id(task)
    errors: list[str] = []
    recommendations: list[str] = []
    rules: dict[str, bool] = {}

    text = _get_task_text(task)

    # 1. Complete YAML frontmatter
    t_id = _get(task, "id")
    t_title = _get(task, "title")
    t_status = _get(task, "status")
    if (
        not t_id
        or not str(t_id).strip()
        or not t_title
        or not str(t_title).strip()
        or not t_status
    ):
        rules[RULE_YAML_FRONTMATTER] = False
        errors.append(
            "Missing complete YAML frontmatter: id, title, and status are required"
        )
    else:
        rules[RULE_YAML_FRONTMATTER] = True

    # 2. Defined Target Bounded Context
    target_bc = str(_get(task, "target_bc") or "").strip()
    if not target_bc:
        rules[RULE_BOUNDED_CONTEXT] = False
        errors.append(
            "Missing target bounded context: task frontmatter must include target_bc"
        )
    else:
        rules[RULE_BOUNDED_CONTEXT] = True

    # 3. Feasible File Limit Scope & Single-Responsibility (ADR-0002)
    bcs_raw = _get(task, "target_bcs")
    target_bcs_count = (
        len(bcs_raw)
        if isinstance(bcs_raw, list)
        else (
            len([b for b in target_bc.split(",") if b.strip()])
            if "," in target_bc
            else 1
        )
    )
    bc_mention_match = re.search(
        r"(?:modifying|spanning|spans)\s+(\d+)\s+(?:different\s+)?bounded\s+contexts",
        text,
        re.I,
    )
    bc_count_from_text = int(bc_mention_match.group(1)) if bc_mention_match else 0
    multi_bc = (
        target_bcs_count > 1
        or bc_count_from_text > 1
        or bool(re.search(r"multiple\s+unrelated\s+bounded\s+contexts", text, re.I))
    )

    lines_exceeded = bool(
        re.search(
            r"(?:spanning\s+)?(?:>\s*500|exceeding\s+500)\s+(?:expected\s+)?lines",
            text,
            re.I,
        )
        or re.search(r">\s*500\s+lines", text, re.I)
    )
    expected_lines = _get(task, "expected_lines")
    if isinstance(expected_lines, (int, float)) and expected_lines > 500:
        lines_exceeded = True

    if (
        multi_bc
        or lines_exceeded
        or (strict and (target_bcs_count > 1 or lines_exceeded))
    ):
        rules[RULE_FILE_LIMIT_SCOPE] = False
        errors.append(
            "DoR Scope Violation: Task violates single-responsibility scope (modifying multiple bounded contexts or spanning >500 expected lines). Advice: decompose into thin vertical slices or architectural spikes (ADR-0002)."
        )
        recommendations.append(
            "Decompose into thin vertical slices or architectural spikes (ADR-0002)."
        )
    else:
        rules[RULE_FILE_LIMIT_SCOPE] = True

    # 4. Cited Governing ADRs
    governing_adrs = _get(task, "governing_adrs") or []
    if isinstance(governing_adrs, str):
        governing_adrs = [governing_adrs]
    adr_errors: list[str] = []
    if not governing_adrs:
        adr_errors.append(
            "Missing governing ADRs: task must link at least 1 accepted ADR"
        )
    else:
        adrs_dir = getattr(config, "adr_dir", None)
        if not adrs_dir:
            adrs_dir = Path(config.project.docs_dir) / "adrs"
            if not adrs_dir.is_absolute():
                adrs_dir = config.root_dir / adrs_dir
        for adr_ref in governing_adrs:
            clean_num = str(adr_ref).upper().replace("ADR-", "").lstrip("0") or "0"
            target_stem = clean_num.zfill(4)
            found = False
            if adrs_dir.exists():
                for p in adrs_dir.rglob("*.md"):
                    if (
                        target_stem in p.stem.upper()
                        or str(adr_ref).upper() in p.name.upper()
                    ) and p.is_file():
                        if p.parent.name.lower() == "accepted":
                            found = True
                            break
                        meta, _ = extract_frontmatter(p.read_text(encoding="utf-8"))
                        if str(meta.get("status", "")).strip().lower() == "accepted":
                            found = True
                            break
            if not found:
                adr_errors.append(
                    f"Missing governing ADRs: task must link at least 1 accepted ADR ({adr_ref} not found in accepted/)"
                )

    if adr_errors:
        rules[RULE_GOVERNING_ADRS] = False
        errors.extend(adr_errors)
    else:
        rules[RULE_GOVERNING_ADRS] = True

    # 5. Linked Persona & PRD
    governing_prds = _get(task, "governing_prds") or []
    if isinstance(governing_prds, str):
        governing_prds = [governing_prds]
    prd_errors: list[str] = []
    found_prds: list[Path] = []
    if not governing_prds:
        prd_errors.append(
            "Missing governing PRD: task must link at least 1 accepted PRD"
        )
    else:
        prd_dir = getattr(config, "prd_dir", None)
        if not prd_dir:
            prd_dir = Path(config.project.docs_dir) / "product"
            if not prd_dir.is_absolute():
                prd_dir = config.root_dir / prd_dir
        for prd_ref in governing_prds:
            clean_p = str(prd_ref).upper().replace("PRD-", "").lstrip("0") or "0"
            target_stem = clean_p.zfill(4)
            found = False
            if prd_dir.exists():
                for p in prd_dir.rglob("*.md"):
                    if (
                        target_stem in p.stem.upper()
                        or str(prd_ref).upper() in p.name.upper()
                    ) and p.is_file():
                        if p.parent.name.lower() in ("accepted", "shipped"):
                            found = True
                            found_prds.append(p)
                            break
                        meta, _ = extract_frontmatter(p.read_text(encoding="utf-8"))
                        if str(meta.get("status", "")).strip().lower() in (
                            "accepted",
                            "shipped",
                        ):
                            found = True
                            found_prds.append(p)
                            break
            if not found:
                prd_errors.append(
                    f"Missing governing PRD: task must link at least 1 accepted PRD ({prd_ref} not found in accepted/)"
                )

    # Persona check
    stories_dir = getattr(config, "user_stories_dir", None)
    if not stories_dir:
        stories_dir = Path(config.project.docs_dir) / "user_stories"
        if not stories_dir.is_absolute():
            stories_dir = config.root_dir / stories_dir

    personas_set = set(KNOWN_PERSONAS)
    personas_file = stories_dir / "PERSONAS.md"
    if personas_file.is_file():
        try:
            p_content = personas_file.read_text(encoding="utf-8")
            for m in re.finditer(r"##\s+\d+\.\s+([A-Za-z]+)", p_content):
                personas_set.add(m.group(1).lower())
        except OSError:
            pass

    persona = _get(task, "persona") or _get(task, "target_persona")
    persona_found = bool(persona and str(persona).strip())
    if not persona_found:
        for kp in personas_set:
            if re.search(rf"\b{kp}\b", text, re.I):
                persona_found = True
                break
    if not persona_found and re.search(
        r"(?:persona|as a)\s*[:—]\s*([a-zA-Z]+)", text, re.I
    ):
        persona_found = True

    governing_stories = _get(task, "governing_stories") or []
    if isinstance(governing_stories, str):
        governing_stories = [governing_stories]
    found_stories: list[Path] = []
    if stories_dir.exists():
        for s_ref in governing_stories:
            clean_s = str(s_ref).upper().replace("US-", "").lstrip("0") or "0"
            target_stem = clean_s.zfill(4)
            for p in stories_dir.rglob("*.md"):
                if (
                    target_stem in p.stem.upper()
                    or str(s_ref).upper() in p.name.upper()
                ) and p.is_file():
                    found_stories.append(p)
                    if not persona_found:
                        meta, _ = extract_frontmatter(p.read_text(encoding="utf-8"))
                        if meta.get("persona"):
                            persona_found = True
                    break

    if not persona_found:
        for p_file in found_prds:
            meta, _ = extract_frontmatter(p_file.read_text(encoding="utf-8"))
            if meta.get("target_persona") or meta.get("persona"):
                persona_found = True
                break

    if not persona_found:
        prd_errors.append(
            "Missing linked persona: task, governing story, or PRD must reference a valid persona from PERSONAS.md"
        )

    if prd_errors:
        rules[RULE_PERSONA_PRD] = False
        errors.extend(prd_errors)
    else:
        rules[RULE_PERSONA_PRD] = True

    # 6. Executable Gherkin Scenarios & Governing Stories (ADR-0006)
    has_gherkin = bool(
        re.search(r"\bgiven\b", text, re.I)
        and re.search(r"\bwhen\b", text, re.I)
        and re.search(r"\bthen\b", text, re.I)
    )
    if not has_gherkin:
        if not governing_stories:
            errors.append(
                "Missing governing story: task must trace back to an accepted BDD user story"
            )
        for s_file in found_stories:
            s_content = s_file.read_text(encoding="utf-8")
            if (
                re.search(r"\bgiven\b", s_content, re.I)
                and re.search(r"\bwhen\b", s_content, re.I)
                and re.search(r"\bthen\b", s_content, re.I)
            ):
                has_gherkin = True
                break

    if not has_gherkin:
        rules[RULE_GHERKIN_SCENARIOS] = False
        errors.append(
            f"{task_id}: DoR Violation - Missing executable Gherkin acceptance criteria (ADR-0006)"
        )
    else:
        rules[RULE_GHERKIN_SCENARIOS] = True

    # 7. Mutation Testing Scope Defined (ADR-0009)
    mutation_scope = _get(task, "mutation_scope")
    has_mutation = bool(
        (
            mutation_scope is not None
            and (mutation_scope != "" or isinstance(mutation_scope, list))
        )
        or re.search(r"\bmutmut\b", text, re.I)
        or re.search(r"\bmutation\s+(?:testing\s+)?scope\b", text, re.I)
    )
    if not has_mutation:
        rules[RULE_MUTATION_SCOPE] = False
        errors.append(
            "Missing mutation testing scope: task must identify target modules for mutmut mutation testing (ADR-0009)"
        )
    else:
        rules[RULE_MUTATION_SCOPE] = True

    is_ready = len(errors) == 0 and all(rules.get(r, False) for r in ALL_DOR_RULES)
    return DoRAuditReport(
        task_id=task_id,
        is_ready=is_ready,
        rules=rules,
        errors=errors,
        recommendations=recommendations,
    )


def validate_task_dor(
    task: Task | dict[str, Any], config: SpecOpsConfig, strict: bool = False
) -> tuple[bool, list[str]]:
    """Validates that a task satisfies all Definition of Ready (DoR) criteria."""
    report = audit_task_health(task, config, strict=strict)
    return report.is_ready, report.errors
