"""Interactive guided initialization wizard and dry-run preview engine."""

from __future__ import annotations

import hashlib
import json
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore

from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.syntax import Syntax
from rich.tree import Tree

from ..profiles.composer import ResolvedComposition, compose_profiles, load_profile_definition
from ..profiles.models import BaselineADR, ProfileError
from ..profiles.registry import PROFILES, get_profile
from .adapters import parse_target_agents


class InitValidationError(Exception):
    """Raised when project initialization parameters fail validation."""


@dataclass
class WizardConfig:
    name: str
    target_dir: Path
    profiles: list[str] = field(default_factory=lambda: ["core", "bdd", "ddd"])
    bounded_contexts: list[str] = field(default_factory=list)
    ci: str = "github"
    diataxis: bool = True
    github_pages: bool = True
    pre_commit: bool = True
    agents: list[str] | str | None = None
    dry_run: bool = False
    interactive: bool = False
    yes: bool = False


@dataclass
class InitializationPlan:
    config: WizardConfig
    composition: ResolvedComposition
    specops_toml: str
    config_ast: dict[str, Any]
    planned_files: list[str]
    adrs: list[BaselineADR]
    collisions: list[str]
    checksums: dict[str, str]


def compute_profile_checksums(profile_ids: list[str]) -> dict[str, str]:
    """Calculates deterministic SHA256 checksums for architectural profiles."""
    checksums: dict[str, str] = {}
    for pid in profile_ids:
        prof = get_profile(pid)
        if prof:
            data = f"{prof.id}:{prof.name}:{prof.version}\n" + "".join(
                f"{a.number}:{a.slug}:{a.content}\n" for a in prof.adrs
            )
            checksums[pid] = hashlib.sha256(data.encode("utf-8")).hexdigest()
        else:
            checksums[pid] = hashlib.sha256(pid.encode("utf-8")).hexdigest()
    return checksums


def validate_init_options(
    project_name: str,
    profiles: list[str],
    bounded_contexts: list[str],
    target_dir: Path,
) -> None:
    """Validates initialization parameters against architectural constraints."""
    if not project_name or not project_name.strip():
        raise InitValidationError("Project name cannot be empty.")
    if "\0" in project_name:
        raise InitValidationError("Illegal project name containing null bytes.")
    if any(c in project_name for c in ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]):
        raise InitValidationError(f"Illegal project name '{project_name}': contains forbidden characters.")
    if "\0" in str(target_dir):
        raise InitValidationError("Illegal directory name containing null bytes.")
    if not profiles:
        raise InitValidationError("At least one architectural profile must be specified.")

    for p in profiles:
        p_clean = p.strip()
        if p_clean:
            try:
                load_profile_definition(p_clean)
            except ProfileError:
                avail = ", ".join(sorted(PROFILES.keys()))
                raise InitValidationError(
                    f"Unknown or invalid architectural profile: '{p_clean}'. Available profiles: {avail}."
                )

    seen_bcs: set[str] = set()
    for bc in bounded_contexts:
        bc_clean = bc.strip()
        if not bc_clean:
            continue
        bc_lower = bc_clean.lower()
        if bc_lower == "core":
            raise InitValidationError("Duplicate bounded context declared: 'core' is the reserved baseline component.")
        if bc_lower in seen_bcs:
            raise InitValidationError(f"Duplicate bounded context declared: '{bc_clean}'.")
        seen_bcs.add(bc_lower)
        if not re.match(r"^[a-zA-Z0-9_\-]+$", bc_clean):
            raise InitValidationError(
                f"Illegal bounded context identifier '{bc_clean}': must contain only alphanumeric characters, underscores, or hyphens."
            )


def serialize_specops_toml(
    composition: ResolvedComposition,
    project_name: str,
    bounded_contexts: list[str] | None = None,
    agents: list[str] | None = None,
) -> str:
    """Serializes a specops.toml configuration string matching composition rules."""
    from .init import DEFAULT_SPECOPS_TOML

    content = DEFAULT_SPECOPS_TOML.format(name=project_name)
    if composition.file_length_limit != 500:
        content = re.sub(r"file_length_limit\s*=\s*\d+", f"file_length_limit = {composition.file_length_limit}", content)

    qual_overrides = composition.overrides.get("quality", {})
    if qual_overrides.get("require_mutation_testing") and "require_mutation_testing" not in content:
        content = content.replace("require_bdd = true", "require_bdd = true\nrequire_mutation_testing = true")

    if bounded_contexts:
        bc_entries = [
            f'  {{ id = "{bc}", name = "{bc.replace("_", " ").replace("-", " ").title()}", path = "src/{bc}" }}'
            for bc in bounded_contexts
        ]
        content = content.replace(
            '  { id = "core", name = "Core Engine", path = "src" }\n]',
            '  { id = "core", name = "Core Engine", path = "src" },\n' + ",\n".join(bc_entries) + "\n]",
        )

    if composition.slices:
        extra_slices = ",\n".join(
            f'  {{ type = "{s.type}", name = "{s.name}", prefix = "{s.prefix}", requires_adr = {str(s.requires_adr).lower()} }}'
            for s in composition.slices
        )
        content = content.replace(
            '  { type = "test", name = "Blackbox Frontdoor Test Suite" }\n]',
            f'  {{ type = "test", name = "Blackbox Frontdoor Test Suite" }},\n{extra_slices}\n]',
        )

    if agents:
        content += f'\ntarget_agents = [{", ".join(f"{chr(34)}{a}{chr(34)}" for a in agents)}]\n'

    all_pids = composition.profile_ids or ["core"]
    content += f'\n[profiles]\ninstalled = [{", ".join(f"{chr(34)}{p}{chr(34)}" for p in all_pids)}]\nversion = "{composition.version}"\n'

    if "security" in [p.lower() for p in all_pids]:
        from ..profiles.security import DEFAULT_SECURITY_TOML
        content += f"\n{DEFAULT_SECURITY_TOML.strip()}\n"

    return content


def plan_initialization(config: WizardConfig) -> InitializationPlan:
    """Plans full file manifest, resolves profile composition, and detects collisions."""
    validate_init_options(config.name, config.profiles, config.bounded_contexts, config.target_dir)

    composition = compose_profiles(config.profiles)
    parsed_agents = parse_target_agents(config.agents)
    toml_str = serialize_specops_toml(composition, config.name, bounded_contexts=config.bounded_contexts, agents=parsed_agents)
    config_ast = tomllib.loads(toml_str)

    planned = [
        "specops.toml", "AGENTS.md", "docs/project/user_stories/PERSONAS.md",
        "docs/project/product/REGISTRY.md", "docs/project/user_stories/REGISTRY.md",
        "docs/project/backlog/README.md", "docs/project/backlog/PRIORITY.md",
        "docs/project/backlog/ROADMAP.md", "docs/project/backlog/refined/0001-initial-architecture-spike-and-setup.md",
        "docs/project/adrs/REGISTRY.md", ".gitignore", ".specops-scaffold.json",
        ".agents/skills/spec-ops/SKILL.md", ".agents/skills/spec-ops/references/cli_primer.md",
        ".agents/skills/spec-ops/references/balancing_loop.md", ".agents/skills/spec-ops/references/orchestration_protocol.md",
    ]
    for adr in composition.adrs:
        planned.append(f"docs/project/adrs/accepted/{adr.filename}")
    if "security" in [p.lower() for p in composition.profile_ids]:
        planned.append("docs/project/SECURITY.md")
    for bc in config.bounded_contexts:
        planned.append(f"src/{bc}/__init__.py")
    if config.ci in ("github", "all"):
        planned.append(".github/workflows/ci.yml")
    if config.ci in ("gitlab", "all"):
        planned.append(".gitlab-ci.yml")
    if config.github_pages and config.ci in ("github", "all"):
        planned.append(".github/workflows/deploy-pages.yml")
    if config.pre_commit:
        planned.append(".pre-commit-config.yaml")
    if config.diataxis:
        planned.extend([
            "docs/tutorials/01-getting-started.md", "docs/how-to/bootstrap-project.md",
            "docs/reference/cli.md", "docs/explanation/project-management-as-code.md",
            "docs/contributing.md", "docs/index.md", "docs/operating-manual.md",
        ])
    if parsed_agents:
        if "antigravity" in parsed_agents:
            planned.extend([
                "GEMINI.md", ".agents/skills/curate/SKILL.md",
                ".agents/skills/health/SKILL.md", ".agents/skills/worker/SKILL.md",
            ])
        if "claude" in parsed_agents:
            planned.append("CLAUDE.md")
        if "cursor" in parsed_agents:
            planned.append(".cursorrules")

    target_root = config.target_dir.resolve()
    collisions = [rel for rel in planned if (target_root / rel).exists()]
    checksums = compute_profile_checksums(composition.profile_ids)

    return InitializationPlan(
        config=config,
        composition=composition,
        specops_toml=toml_str,
        config_ast=config_ast,
        planned_files=planned,
        adrs=composition.adrs,
        collisions=collisions,
        checksums=checksums,
    )


def render_preview_tree(plan: InitializationPlan, console: Console) -> None:
    """Renders a Rich tree summarizing planned directories and baseline ADRs."""
    tree = Tree(f"[bold cyan]{plan.config.name}/[/bold cyan] (Planned Manifest)")
    folders: dict[str, Any] = {}
    for p in sorted(plan.planned_files):
        parts = Path(p).parts
        if len(parts) == 1:
            tree.add(f"[green]{parts[0]}[/green]")
        else:
            curr = tree
            accum = ""
            for seg in parts[:-1]:
                accum = f"{accum}/{seg}" if accum else seg
                if accum not in folders:
                    folders[accum] = curr.add(f"[bold blue]{seg}/[/bold blue]")
                curr = folders[accum]
            curr.add(f"[white]{parts[-1]}[/white]")
    console.print(tree)


def render_dry_run(plan: InitializationPlan, console: Console | None = None) -> None:
    """Renders a complete dry-run initialization preview to the console."""
    con = console or Console()
    con.print("[bold cyan]=== SpecOps Initialization Dry-Run Preview ===[/bold cyan]")
    con.print(f"📦 [bold]Project:[/bold] {plan.config.name}")
    con.print(f"🎯 [bold]Target Directory:[/bold] {plan.config.target_dir.resolve()}")
    con.print(f"📋 [bold]Detected Profiles:[/bold] {', '.join(plan.config.profiles)}")
    con.print(f"🛡️  [bold]Baseline ADRs:[/bold] {len(plan.adrs)} resolved")

    if plan.collisions:
        con.print(f"[yellow]⚠️  Potential Filename Collisions ({len(plan.collisions)}):[/yellow]")
        for c in plan.collisions:
            con.print(f"   - {c}")
    else:
        con.print("✨ [green]Filename Collisions:[/green] None (clean directory)")

    con.print("\n[bold]Planned File Manifest Tree:[/bold]")
    render_preview_tree(plan, con)
    con.print("\n[bold]Generated specops.toml:[/bold]")
    con.print(Syntax(plan.specops_toml, "toml", theme="monokai", line_numbers=True))
    con.print("\n[green]✅ Dry-run complete. Zero files were created on disk.[/green]")


def run_interactive_wizard(
    default_dir: Path,
    default_name: str | None = None,
    console: Console | None = None,
) -> WizardConfig | None:
    """Guides user through interactive prompts, live preview, and confirmation."""
    con = console or Console()
    con.print("[bold cyan]🧙 SpecOps Interactive Guided Initialization Wizard[/bold cyan]\n")

    initial_name = default_name or default_dir.resolve().name
    name = Prompt.ask("Project name", default=initial_name, console=con)

    profiles_raw = Prompt.ask(
        "Architectural profiles (comma-separated: core, bdd, ddd, security)",
        default="core,bdd,ddd",
        console=con,
    )
    profiles = [p.strip() for p in profiles_raw.split(",") if p.strip()]

    bc_raw = Prompt.ask("Initial bounded contexts (comma-separated, optional)", default="", console=con)
    bcs = [b.strip() for b in bc_raw.split(",") if b.strip()]

    ci = Prompt.ask("CI provider (github, gitlab, or none)", choices=["github", "gitlab", "none", "all"], default="github", console=con)
    diataxis = Confirm.ask("Scaffold Diataxis 4-quadrant documentation?", default=True, console=con)

    cfg = WizardConfig(
        name=name, target_dir=default_dir, profiles=profiles,
        bounded_contexts=bcs, ci=ci, diataxis=diataxis, interactive=True,
    )

    plan = plan_initialization(cfg)
    con.print("\n[bold green]📄 Live specops.toml Preview:[/bold green]")
    con.print(Syntax(plan.specops_toml, "toml", theme="monokai", line_numbers=True))
    con.print("\n[bold]Planned File & Baseline ADR Manifest:[/bold]")
    render_preview_tree(plan, con)

    confirmed = Confirm.ask("\nScaffold SpecOps repository with this configuration?", default=True, console=con)
    if not confirmed:
        con.print("[yellow]❌ Initialization cancelled by user.[/yellow]")
        return None
    return cfg


def handle_init_command(args: Any, console: Console | None = None) -> int:
    """Entry point for spec-ops init handling interactive, headless, and dry-run modes."""
    from .init import init_project

    con = console or Console()
    target = Path(getattr(args, "dir", ".")).resolve()
    is_interactive = bool(getattr(args, "interactive", False))
    is_headless = bool(getattr(args, "headless", False))
    is_dry_run = bool(getattr(args, "dry_run", False))

    raw_profiles = getattr(args, "profile", "core,bdd,ddd") or "core,bdd,ddd"
    profiles = [p.strip() for p in raw_profiles.split(",") if p.strip()]
    raw_bcs = getattr(args, "bc", None) or []
    bounded_contexts = [b.strip() for item in raw_bcs for b in item.split(",") if b.strip()]
    name = getattr(args, "name", None) or target.name
    ci = getattr(args, "ci", "github") or "github"
    diataxis = bool(getattr(args, "diataxis", True))
    github_pages = bool(getattr(args, "github_pages", True))
    pre_commit = bool(getattr(args, "pre_commit", True))
    agents = getattr(args, "agent", None)

    try:
        if is_interactive:
            cfg = run_interactive_wizard(target, default_name=getattr(args, "name", None), console=con)
            if cfg is None:
                return 0
            config = cfg
        else:
            config = WizardConfig(
                name=name, target_dir=target, profiles=profiles,
                bounded_contexts=bounded_contexts, ci=ci, diataxis=diataxis,
                github_pages=github_pages, pre_commit=pre_commit, agents=agents,
                dry_run=is_dry_run, interactive=False, yes=bool(getattr(args, "yes", False)),
            )

        plan = plan_initialization(config)

        if is_dry_run:
            render_dry_run(plan, con)
            return 0

        created = init_project(
            config.target_dir,
            name=config.name,
            profiles=config.profiles,
            diataxis=config.diataxis,
            github_pages=config.github_pages,
            pre_commit=config.pre_commit,
            agents=config.agents,
            ci=config.ci,
            bounded_contexts=config.bounded_contexts,
        )

        con.print(f"✨ Initialized SpecOps in {config.target_dir}")
        con.print(f"📋 Installed Profiles: {', '.join(config.profiles)}")
        if config.agents:
            parsed = parse_target_agents(config.agents)
            if parsed:
                con.print(f"🤖 Configured Agent Adapters: {', '.join(parsed)}")
        con.print(f"📁 Created {len(created)} file(s) and directory structures.")
        con.print("👉 Run 'spec-ops health' to verify repository invariants.")
        return 0

    except (InitValidationError, ProfileError) as err:
        print(f"❌ Validation error: {err}", file=sys.stderr)
        return 1
    except Exception as err:
        print(f"❌ Initialization error: {err}", file=sys.stderr)
        return 1
