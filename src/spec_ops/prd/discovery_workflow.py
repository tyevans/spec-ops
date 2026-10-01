"""Continuous product discovery and living PRD synthesis workflow."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

from ..config.models import SpecOpsConfig
from ..core.parser import extract_frontmatter
from .discovery import parse_available_personas
from .lifecycle import PRDLifecycleManager
from .linter import PRDLinter


def parse_outcomes_input(outcomes_val: str | list[str] | Path) -> list[str]:
    """Parses outcome strings, file paths, or lists into clean outcome statements."""
    if isinstance(outcomes_val, Path) or (isinstance(outcomes_val, str) and Path(outcomes_val).is_file()):
        raw_text = Path(outcomes_val).read_text(encoding="utf-8")
        raw_lines = raw_text.splitlines()
    elif isinstance(outcomes_val, str):
        if "\n" in outcomes_val:
            raw_lines = outcomes_val.splitlines()
        elif ";" in outcomes_val:
            raw_lines = outcomes_val.split(";")
        elif "," in outcomes_val:
            raw_lines = outcomes_val.split(",")
        else:
            raw_lines = [outcomes_val]
    elif isinstance(outcomes_val, (list, tuple)):
        raw_lines = list(outcomes_val)
    else:
        raw_lines = []

    cleaned: list[str] = []
    for line in raw_lines:
        stripped = str(line).strip()
        if not stripped or stripped.startswith("<!--"):
            continue
        m = re.match(r"^(\d+\.|\-|\*)\s*(.+)$", stripped)
        text = m.group(2).strip() if m else stripped
        if text:
            cleaned.append(text)
    return cleaned


def discover_prd(
    config: SpecOpsConfig,
    title: str | None = None,
    persona: str | None = None,
    bc: str | None = None,
    summary: str | None = None,
    non_interactive: bool = False,
) -> Path:
    """Discovers and scaffolds a new PRD idea draft in docs/project/product/idea/."""
    personas_file = config.user_stories_dir / "PERSONAS.md"
    available_personas = parse_available_personas(personas_file)

    is_interactive = (not non_interactive) and sys.stdin.isatty()

    def ask(prompt_text: str, default: str) -> str:
        if not is_interactive:
            return default
        try:
            val = input(prompt_text).strip()
            return val or default
        except (EOFError, KeyboardInterrupt):
            return default

    if not title:
        title = ask("👉 PRD Title: ", default="New Continuous Discovery Capability")

    if not persona:
        if is_interactive:
            print("\n📋 Target Personas available in docs/project/user_stories/PERSONAS.md:")
            for idx, p_name in enumerate(available_personas, 1):
                print(f"   [{idx}] {p_name}")
            p_ans = ask(
                "\n👉 Target Persona: ",
                default="Taylor (The Product Manager)",
            )
            if p_ans.isdigit() and 1 <= int(p_ans) <= len(available_personas):
                persona = available_personas[int(p_ans) - 1]
            else:
                persona = p_ans
        else:
            persona = available_personas[0] if available_personas else "Taylor (The Product Manager)"

    if not bc:
        bc = ask("👉 Target Component / Bounded Context: ", default="core")

    if not summary:
        summary = ask(
            "👉 Problem statement / customer friction: ",
            default="Users cannot execute this capability without manual workarounds.",
        )

    # Allocate next PRD ID monotonically
    max_id = 0
    if config.prd_dir.exists():
        for p in config.prd_dir.rglob("*.md"):
            m = re.search(r"prd-(\d+)", p.name, re.IGNORECASE)
            if m:
                max_id = max(max_id, int(m.group(1)))
    registry_file = config.prd_dir / "REGISTRY.md"
    if registry_file.exists():
        for line in registry_file.read_text(encoding="utf-8").splitlines():
            m = re.search(r"PRD-(\d+)", line, re.IGNORECASE)
            if m:
                max_id = max(max_id, int(m.group(1)))

    clean_num = f"{(max_id + 1):04d}"
    canonical_id = f"PRD-{clean_num}"

    slug = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")
    slug = re.sub(r"-+", "-", slug)[:45].strip("-") or "capability"
    filename = f"prd-{clean_num}-{slug}.md"

    target_dir = config.prd_dir / "idea"
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / filename

    today = date.today().isoformat()
    content = f"""---
id: '{clean_num}'
title: {title}
status: Idea
created: {today}
target_persona: {persona}
component: {bc}
---

# {canonical_id} — {title}

## Who this is for

- **{persona}**: {summary}

## What the person cannot do today

- {summary}

## What good looks like

1. **Core Capability**:
   - Automated workflow and verifiable contract for {title}.

## What this does not do

- Scope boundary: does not support ad-hoc private backdoor access.

## Checkable Outcomes

1. Executing public CLI command for {title} returns exit code 0 and valid output.

## Linked User Stories

<!-- Added during decomposition -->

## Implementing Backlog Tasks

<!-- Added during decomposition -->
"""
    file_path.write_text(content, encoding="utf-8")

    lifecycle = PRDLifecycleManager(config)
    lifecycle.update_registry(
        prd_id=canonical_id,
        title=title,
        status="Idea",
        persona=persona,
        component=bc,
    )

    return file_path


def shape_prd(
    config: SpecOpsConfig,
    prd_id_or_path: str | Path,
    outcomes: str | list[str] | Path | None = None,
    anti_goals: str | list[str] | None = None,
    target_stage: str | None = None,
    accept: bool = False,
) -> tuple[bool, str]:
    """Shapes a PRD idea draft, validates sections & falsifiable outcomes, and promotes stage."""
    lifecycle = PRDLifecycleManager(config)
    prd_file = lifecycle.find_prd_file(prd_id_or_path)
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

    if accept:
        effective_stage = "accepted"
    elif target_stage:
        effective_stage = target_stage.strip().lower()
    else:
        curr_status = str(meta.get("status", "")).strip().lower()
        if prd_file.parent.name.lower() == "shaped" or curr_status == "shaped":
            effective_stage = "accepted"
        else:
            effective_stage = "shaped"

    if not persona.strip() or persona.strip().lower() in ("unmapped", "none", "unknown"):
        return False, f"❌ Stage-gate violation error: PRD {canonical_id} target persona is unmapped."

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
            f"❌ Stage-gate violation error: PRD {canonical_id} must define user pain points before promotion.",
        )

    # 1. Update anti-goals if provided
    if anti_goals:
        if isinstance(anti_goals, str):
            if "\n" in anti_goals:
                ag_lines = [l.strip() for l in anti_goals.splitlines() if l.strip()]
            elif "," in anti_goals:
                ag_lines = [l.strip() for l in anti_goals.split(",") if l.strip()]
            else:
                ag_lines = [anti_goals.strip()]
        else:
            ag_lines = [str(a).strip() for a in anti_goals if str(a).strip()]

        clean_ags = []
        for ag in ag_lines:
            m = re.match(r"^(\d+\.|\-|\*)\s*(.+)$", ag)
            clean_ags.append(m.group(2).strip() if m else ag)

        ag_block = "\n".join(f"- {ag}" for ag in clean_ags)
        new_ag_sec = f"## What this does not do\n\n{ag_block}\n"
        if re.search(r"## What this does not do\b", content, re.IGNORECASE):
            content = re.sub(
                r"## What this does not do\s*\n.*?(?=\n##|$)",
                new_ag_sec,
                content,
                flags=re.DOTALL,
            )
        else:
            content += f"\n{new_ag_sec}"

    # 2. Update checkable outcomes
    if outcomes is not None:
        cleaned_outcomes = parse_outcomes_input(outcomes)
        if len(cleaned_outcomes) < 3:
            return (
                False,
                f"❌ Stage-gate violation error: PRD {canonical_id} requires at least 3 checkable outcomes (found {len(cleaned_outcomes)}).",
            )
        outcomes_block = "\n".join(f"{idx}. {oc}" for idx, oc in enumerate(cleaned_outcomes, 1))
        new_outcomes_sec = f"## Checkable Outcomes\n\n{outcomes_block}\n"
        if re.search(r"## Checkable Outcomes\b", content, re.IGNORECASE):
            content = re.sub(
                r"## Checkable Outcomes\s*\n.*?(?=\n##|$)",
                new_outcomes_sec,
                content,
                flags=re.DOTALL,
            )
        else:
            content += f"\n{new_outcomes_sec}"
    else:
        linter = PRDLinter(config.root_dir)
        lint_check = linter.lint_text(content, file_path=prd_file)
        existing_outcomes = [oc.text for oc in lint_check.outcome_checks]
        if len(existing_outcomes) < 3:
            generated_defaults = [
                f"Executing public CLI command for {title} returns exit code 0 and valid output.",
                f"Verification suite passes with 100% frontdoor contract assertions and zero backdoor mocks.",
                f"Relational graph and registry reflect {canonical_id} state transition in component {component}.",
            ]
            combined = list(existing_outcomes)
            for default_oc in generated_defaults:
                if len(combined) >= 3:
                    break
                if default_oc not in combined:
                    combined.append(default_oc)
            outcomes_block = "\n".join(f"{idx}. {oc}" for idx, oc in enumerate(combined, 1))
            new_outcomes_sec = f"## Checkable Outcomes\n\n{outcomes_block}\n"
            if re.search(r"## Checkable Outcomes\b", content, re.IGNORECASE):
                content = re.sub(
                    r"## Checkable Outcomes\s*\n.*?(?=\n##|$)",
                    new_outcomes_sec,
                    content,
                    flags=re.DOTALL,
                )
            else:
                content += f"\n{new_outcomes_sec}"

    prd_file.write_text(content, encoding="utf-8")

    linter = PRDLinter(config.root_dir)
    lint_res = linter.lint_file(prd_file)
    if not lint_res.is_valid:
        err_lines = [f"❌ Stage-gate violation error: Promotion to '{effective_stage}' blocked for {canonical_id}:"]
        for v in lint_res.violations:
            err_lines.append(f"   - {v.message}")
        return False, "\n".join(err_lines)

    falsifiable_outcomes = [oc for oc in lint_res.outcome_checks if oc.is_falsifiable]
    if len(falsifiable_outcomes) < 3:
        return (
            False,
            f"❌ Stage-gate violation error: PRD {canonical_id} requires at least 3 falsifiable checkable outcomes (found {len(falsifiable_outcomes)}).",
        )

    ok, msg = lifecycle.promote(prd_file, effective_stage)
    if not ok:
        return False, msg

    return True, msg
