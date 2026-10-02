"""Autonomous User Persona Journey Friction Auditor and Heuristic Evaluator."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any

from ..core.persona_models import PersonaDocument, PersonaProfile
from ..docs.cli_inspector import extract_parser_commands
from ..docs.models import ParsedCLICommand

CANONICAL_PERSONA_DOMAINS: dict[str, list[str]] = {
    "alex": ["health", "graph", "decompose", "profiles", "check", "adr"],
    "jordan": ["queue", "visualizer", "stats", "release", "report", "curate"],
    "morgan": ["worker", "claim", "rescue", "task", "cycle", "orchestrate"],
    "riley": ["rescue", "check", "worktree", "spike", "review"],
    "taylor": ["prd", "story", "roadmap", "visualizer", "journey", "uat"],
    "sasha": ["security", "audit", "review", "sentinel", "lock"],
}


def compute_friction_index(
    depth: int,
    positionals_count: int,
    options_count: int,
    has_json: bool = True,
    has_non_interactive: bool = True,
    persona_role: str = "",
) -> float:
    """Calculates a deterministic cognitive friction score bounded in [0.0, 10.0]."""
    safe_depth = max(1, depth)
    safe_pos = max(0, positionals_count)
    safe_opts = max(0, options_count)

    # Base ceremony score
    score = (safe_depth - 1) * 0.8
    score += safe_pos * 1.2
    score += min(2.5, safe_opts * 0.2)

    # Persona role heuristics
    role_lower = persona_role.lower()
    if "agent" in role_lower or "autonomous" in role_lower:
        if not has_json:
            score += 2.0
        if not has_non_interactive:
            score += 1.5
    elif "product" in role_lower or "manager" in role_lower or "business" in role_lower:
        if safe_pos >= 2:
            score += 1.8
        if safe_depth >= 3:
            score += 1.5
        if safe_opts >= 5:
            score += 1.0
    elif "human" in role_lower or "developer" in role_lower or "engineer" in role_lower:
        if safe_pos >= 2:
            score += 1.0
        if safe_opts >= 8:
            score += 1.0
    elif "security" in role_lower or "trust" in role_lower:
        if safe_opts < 2:
            score += 0.5

    # Strict invariant clamp to [0.0, 10.0]
    score = max(0.0, min(10.0, score))
    return round(score, 2)


def generate_recommendations(
    cmd_name: str,
    options: set[str],
    positionals: list[str],
    persona: PersonaProfile,
    friction_score: float,
) -> list[str]:
    """Generates actionable UX and CLI ergonomic recommendations."""
    if friction_score < 3.0:
        return ["Command ceremony is within optimal ergonomic thresholds."]

    recs: list[str] = []
    role_lower = f"{persona.role} {persona.role_description}".lower()
    parts = cmd_name.split()

    if len(parts) >= 3:
        alias_candidate = f"spec-ops {parts[-1]}"
        recs.append(f"Introduce top-level alias (e.g. '{alias_candidate}') to reduce nesting depth.")

    if len(positionals) >= 2:
        recs.append(f"Consolidate positional arguments ({', '.join(positionals)}) using smart inference or interactive selection.")
    elif len(positionals) == 1:
        recs.append("Support context-aware default target when positional argument is omitted.")

    if len(options) > 6:
        recs.append("Group excessive optional flags into sensible presets or configuration profiles.")

    if ("agent" in role_lower or "autonomous" in role_lower) and "--json" not in options:
        recs.append("Add '--json' flag to allow structured headless consumption by autonomous agents.")

    if ("product" in role_lower or "manager" in role_lower) and len(positionals) >= 1:
        recs.append("Provide interactive wizard or Web Studio counterpart to avoid terminal friction.")

    if not recs:
        recs.append("Review flag defaults to reduce required cognitive input ceremony.")

    return recs


@dataclass
class WorkflowFriction:
    command: str
    persona_id: str
    persona_name: str
    persona_role: str
    base_score: float
    friction_score: float
    factors: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "persona_id": self.persona_id,
            "persona_name": self.persona_name,
            "persona_role": self.persona_role,
            "base_score": self.base_score,
            "friction_score": self.friction_score,
            "factors": list(self.factors),
            "recommendations": list(self.recommendations),
        }


@dataclass
class FrictionAuditReport:
    workflows: list[WorkflowFriction] = field(default_factory=list)
    personas_audited: list[str] = field(default_factory=list)
    average_friction: float = 0.0
    threshold: float | None = None
    flagged_count: int = 0

    @property
    def has_violations(self) -> bool:
        return self.flagged_count > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "personas_audited": self.personas_audited,
            "evaluated_touchpoints": len(self.workflows),
            "average_friction": self.average_friction,
            "threshold": self.threshold,
            "flagged_count": self.flagged_count,
            "workflows": [w.to_dict() for w in self.workflows],
        }

    def format_text(self) -> str:
        lines: list[str] = [
            "=== SpecOps Persona Journey Friction Audit ===",
            f"Audited Personas: {', '.join(self.personas_audited) if self.personas_audited else 'None'}",
            f"Evaluated Touchpoints: {len(self.workflows)} workflows",
            f"Average Friction Index: {self.average_friction:.2f} / 10.0",
            "",
        ]

        flagged = [w for w in self.workflows if self.threshold is not None and w.friction_score >= self.threshold]
        if self.threshold is not None:
            lines.append(f"High-Friction Touchpoints (Threshold >= {self.threshold:.1f}):")
            if not flagged:
                lines.append("  ✅ No workflows exceed configured friction threshold.")
            else:
                for w in flagged:
                    lines.append(f"  ⚠️  [Score {w.friction_score:.2f}] {w.command} (Persona: {w.persona_name} — {w.persona_role})")
                    if w.factors:
                        lines.append(f"     Factors: {', '.join(w.factors)}")
                    if w.recommendations:
                        lines.append("     Recommendations:")
                        for r in w.recommendations:
                            lines.append(f"       - {r}")
            lines.append("")
            lines.append(f"Status: {len(flagged)} workflow(s) flagged exceeding threshold ({self.threshold:.1f}).")
        else:
            top_friction = sorted(self.workflows, key=lambda w: w.friction_score, reverse=True)[:5]
            lines.append("Top Friction Touchpoints:")
            for w in top_friction:
                lines.append(f"  • [Score {w.friction_score:.2f}] {w.command} ({w.persona_name})")
                for r in w.recommendations[:2]:
                    lines.append(f"     - {r}")
            lines.append("")
            lines.append("Status: Audit completed cleanly.")

        return "\n".join(lines)


_DEFAULT_PARSER_FACTORY: Any = None


def register_default_parser_factory(factory: Any) -> None:
    """Registers an external CLI parser factory callback for dependency inversion."""
    global _DEFAULT_PARSER_FACTORY
    _DEFAULT_PARSER_FACTORY = factory


class PersonaFrictionAuditor:
    """Evaluates cognitive friction and operational ceremony across user persona touchpoints."""

    def __init__(
        self,
        root_dir: Path | None = None,
        personas_doc: PersonaDocument | None = None,
    ) -> None:
        self.root_dir = root_dir or Path.cwd()
        self.personas_doc = personas_doc

    def load_personas(self) -> list[PersonaProfile]:
        """Loads canonical personas from document or disk."""
        if self.personas_doc and self.personas_doc.personas:
            return self.personas_doc.personas

        personas_path = self.root_dir / "docs" / "project" / "user_stories" / "PERSONAS.md"
        if personas_path.exists():
            try:
                doc = PersonaDocument.parse(personas_path.read_text(encoding="utf-8"))
                if doc.personas:
                    return doc.personas
            except Exception:
                pass

        # Built-in fallbacks if PERSONAS.md is absent or unparseable
        return [
            PersonaProfile(name="Alex", role="The Agentic Systems Architect", role_description="Platform architect"),
            PersonaProfile(name="Jordan", role="The AI-Native Engineering Lead", role_description="Product and lead"),
            PersonaProfile(name="Morgan", role="The Autonomous Coding Agent", role_description="Autonomous coding agent"),
            PersonaProfile(name="Riley", role="The Human IC Developer", role_description="Software engineer"),
            PersonaProfile(name="Taylor", role="The Product Manager", role_description="Product manager"),
            PersonaProfile(name="Sasha", role="The Trust & Security Officer", role_description="Security engineer"),
        ]

    def audit(
        self,
        parser: argparse.ArgumentParser | None = None,
        persona_filter: str | None = None,
        threshold: float | None = None,
        commands_override: dict[str, ParsedCLICommand] | None = None,
    ) -> FrictionAuditReport:
        """Runs the heuristic friction audit across CLI commands and persona profiles."""
        personas = self.load_personas()
        if persona_filter:
            filt = persona_filter.strip().lower()
            personas = [p for p in personas if filt in p.name.lower() or filt in p.id.lower()]

        if commands_override is not None:
            commands = commands_override
        elif parser is not None:
            commands = extract_parser_commands(parser)
        else:
            factory = _DEFAULT_PARSER_FACTORY
            if factory is not None:
                commands = extract_parser_commands(factory())
            else:
                try:
                    import importlib
                    cli_mod = importlib.import_module("spec_ops.cli.parser")
                    build_fn = getattr(cli_mod, "build_parser")
                    commands = extract_parser_commands(build_fn())
                except Exception:
                    commands = {}

        workflows: list[WorkflowFriction] = []

        for p in personas:
            p_id = p.id.lower()
            relevant_domains = CANONICAL_PERSONA_DOMAINS.get(p_id, [])

            for cmd_name, cmd_info in commands.items():
                if cmd_name == "spec-ops":
                    continue

                # Filter commands relevant to persona domains if defined
                if relevant_domains:
                    is_relevant = any(dom in cmd_name for dom in relevant_domains)
                    if not is_relevant:
                        continue

                parts = cmd_name.split()
                depth = len(parts)
                opts = cmd_info.options
                pos = cmd_info.positionals

                has_json = any("--json" in opt for opt in opts)
                has_non_int = any("non-interactive" in opt or "--batch" in opt or "--auto" in opt for opt in opts)

                base_score = compute_friction_index(depth, len(pos), len(opts), True, True, "")
                friction_score = compute_friction_index(
                    depth,
                    len(pos),
                    len(opts),
                    has_json=has_json,
                    has_non_interactive=has_non_int,
                    persona_role=f"{p.role} {p.role_description}",
                )

                factors: list[str] = [f"Depth {depth}", f"{len(pos)} positional(s)", f"{len(opts)} option(s)"]
                if not has_json and ("agent" in p.role.lower() or "agent" in p.role_description.lower()):
                    factors.append("Missing machine-readable --json flag")
                if len(pos) >= 2 and ("product" in p.role.lower() or "product" in p.role_description.lower()):
                    factors.append("Multi-positional CLI ceremony")

                recs = generate_recommendations(cmd_name, opts, pos, p, friction_score)

                workflows.append(
                    WorkflowFriction(
                        command=cmd_name,
                        persona_id=p.id,
                        persona_name=p.name,
                        persona_role=p.role,
                        base_score=base_score,
                        friction_score=friction_score,
                        factors=factors,
                        recommendations=recs,
                    )
                )

        avg_friction = (
            round(sum(w.friction_score for w in workflows) / len(workflows), 2)
            if workflows
            else 0.0
        )
        flagged_count = (
            sum(1 for w in workflows if threshold is not None and w.friction_score >= threshold)
        )

        return FrictionAuditReport(
            workflows=workflows,
            personas_audited=[p.name for p in personas],
            average_friction=avg_friction,
            threshold=threshold,
            flagged_count=flagged_count,
        )
