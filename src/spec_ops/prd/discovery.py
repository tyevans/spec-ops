"""Interactive PRD discovery guide and scaffolding workflow."""

from __future__ import annotations

import re
import sys
from datetime import date
from pathlib import Path

from ..config.models import SpecOpsConfig
from .lifecycle import PRDLifecycleManager


def parse_available_personas(personas_file: Path) -> list[str]:
    """Extracts persona names from PERSONAS.md."""
    if not personas_file.is_file():
        return [
            "Alex (The Agentic Systems Architect)",
            "Jordan (The AI-Native Engineering Lead)",
            "Morgan (The Autonomous Coding Agent)",
            "Riley (The Human IC Developer)",
            "Taylor (The Product Manager)",
            "Sasha (The Trust & Security Officer)",
        ]
    personas: list[str] = []
    lines = personas_file.read_text(encoding="utf-8").splitlines()
    for line in lines:
        m = re.match(r"^##\s+\d+\.\s*(.+)$", line.strip())
        if m:
            personas.append(m.group(1).strip())
    if not personas:
        personas = [
            "Alex (The Agentic Systems Architect)",
            "Jordan (The AI-Native Engineering Lead)",
            "Morgan (The Autonomous Coding Agent)",
            "Riley (The Human IC Developer)",
            "Taylor (The Product Manager)",
            "Sasha (The Trust & Security Officer)",
        ]
    return personas


def interactive_new_prd(
    config: SpecOpsConfig,
    title: str | None = None,
    persona: str | None = None,
    component: str | None = None,
    friction: str | None = None,
    good: str | None = None,
    anti_goals: str | None = None,
    outcomes: str | None = None,
    non_interactive: bool = False,
) -> Path:
    """Interactively guides the user through PRD discovery scaffolding."""
    personas_file = config.user_stories_dir / "PERSONAS.md"
    available_personas = parse_available_personas(personas_file)

    def ask(prompt_text: str, default: str = "") -> str:
        if non_interactive:
            return default
        try:
            val = input(prompt_text).strip()
            return val or default
        except (EOFError, KeyboardInterrupt):
            return default

    # 1. Target Persona
    if not persona:
        print("\n📋 Target Personas available in docs/project/user_stories/PERSONAS.md:")
        for idx, p_name in enumerate(available_personas, 1):
            print(f"   [{idx}] {p_name}")
        p_ans = ask(
            "\n👉 Target Persona (selected from docs/project/user_stories/PERSONAS.md): ",
            default="Taylor (The Product Manager)",
        )
        if p_ans.isdigit() and 1 <= int(p_ans) <= len(available_personas):
            persona = available_personas[int(p_ans) - 1]
        else:
            persona = p_ans

    # 2. PRD Title
    if not title:
        title = ask("👉 PRD Title: ", default="New Product Discovery Capability")

    # 3. Component
    if not component:
        component = ask(
            "👉 Target Component / Bounded Context (default: core): ", default="core"
        )

    # 4. What the person cannot do today
    if not friction:
        friction = ask(
            "👉 What the person cannot do today (customer friction statement): ",
            default="Users cannot execute this capability without manual workarounds.",
        )

    # 5. What good looks like
    if not good:
        good = ask(
            "👉 What good looks like (core capabilities): ",
            default="A fully automated, verifiable workflow through public interfaces.",
        )

    # 6. What this does not do
    if not anti_goals:
        anti_goals = ask(
            "👉 What this does not do (scope boundaries and non-goals): ",
            default="Explicit scope boundary: does not support ad-hoc private backdoor access.",
        )

    # 7. Checkable Outcomes
    if not outcomes:
        outcomes = ask(
            "👉 Checkable Outcomes (at least one observable verification criterion): ",
            default="Executing CLI command returns code 0 and outputs expected structure.",
        )

    # Calculate next ID
    max_id = 0
    if config.prd_dir.exists():
        for p in config.prd_dir.rglob("*.md"):
            m = re.search(r"prd-(\d+)", p.name, re.IGNORECASE)
            if m:
                max_id = max(max_id, int(m.group(1)))
    clean_num = f"{(max_id + 1):04d}"
    prd_id = f"PRD-{clean_num}"

    slug = "".join(c if c.isalnum() else "-" for c in title.lower()).strip("-")
    filename = f"prd-{clean_num}-{slug[:45]}.md"

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
component: {component}
---

# {prd_id} — {title}

## Who this is for

- **{persona}**: {friction}

## What the person cannot do today

- {friction}

## What good looks like

1. **Core Capability**:
   - {good}

## What this does not do

- {anti_goals}

## Checkable Outcomes

1. {outcomes}

## Linked User Stories

<!-- Added during decomposition -->

## Implementing Backlog Tasks

<!-- Added during decomposition -->
"""
    file_path.write_text(content, encoding="utf-8")

    lifecycle = PRDLifecycleManager(config)
    lifecycle.update_registry(
        prd_id=prd_id,
        title=title,
        status="Idea",
        persona=persona,
        component=component,
    )

    return file_path
