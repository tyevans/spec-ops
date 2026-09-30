"""Hierarchical profile composition, inheritance DAG resolution, and invariant overrides engine."""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore

from ..config.models import SliceConfig
from .models import ADRCollisionError, BaselineADR, Profile, ProfileError, ProfileInheritanceError
from .registry import PROFILES, get_profile


@dataclass
class ResolvedComposition:
    profile_ids: list[str]
    adrs: list[BaselineADR]
    overrides: dict[str, Any] = field(default_factory=dict)
    slices: list[SliceConfig] = field(default_factory=list)
    invariants: list[str] = field(default_factory=list)
    version: str = "0.1.0"
    file_length_limit: int = 500


# pragma: no mutate start
def parse_adr_content(content: str, filename: str = "") -> BaselineADR:
    """Parses ADR frontmatter or Markdown heading into a BaselineADR model."""
    number = 0
    slug = ""
    title = ""
    status = "Accepted"
    date = "2026-09-29"

    # Try matching filename first: adr-0004-foo.md
    fn_m = re.match(r"^adr-(\d+)(?:-(.*))?\.md$", filename)
    if fn_m:
        number = int(fn_m.group(1))
        slug = fn_m.group(2) or ""

    # Parse YAML frontmatter if present
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", content, re.DOTALL)
    body = content
    if fm_match:
        fm_text = fm_match.group(1)
        body = fm_match.group(2)
        for line in fm_text.splitlines():
            line = line.strip()
            if line.startswith("id:"):
                val = line.split(":", 1)[1].strip().strip("'\"")
                try:
                    number = int(val)
                except ValueError:
                    m = re.search(r"\d+", val)
                    if m:
                        number = int(m.group(0))
            elif line.startswith("title:"):
                title = line.split(":", 1)[1].strip().strip("'\"")
            elif line.startswith("status:"):
                status = line.split(":", 1)[1].strip().strip("'\"")
            elif line.startswith("date:"):
                date = line.split(":", 1)[1].strip().strip("'\"")

    # If title not found in frontmatter, search body
    if not title:
        t_m = re.search(r"^#\s*(?:ADR-(\d+)[:\s-]*)?(.*)$", body, re.MULTILINE)
        if t_m:
            if t_m.group(1) and number == 0:
                number = int(t_m.group(1))
            title = t_m.group(2).strip()

    if not title:
        title = slug.replace("-", " ").title() if slug else f"ADR {number:04d}"

    if not slug:
        slug = re.sub(r"[^\w\s-]", "", title.lower()).strip()
        slug = re.sub(r"[\s_]+", "-", slug)

    return BaselineADR(
        number=number,
        slug=slug,
        title=title,
        status=status,
        date=date,
        content=content.strip() + "\n",
    )


def parse_profile_toml(toml_content: str, base_dir: Path | None = None) -> Profile:
    """Parses a profile.toml string into a Profile instance."""
    data = tomllib.loads(toml_content)
    prof_data = data.get("profile", {})
    p_id = str(prof_data.get("id") or data.get("id") or (base_dir.name if base_dir else "custom"))
    name = str(prof_data.get("name") or data.get("name") or p_id)
    version = str(prof_data.get("version") or data.get("version") or "0.1.0")
    description = str(prof_data.get("description") or data.get("description") or "")
    extends_raw = prof_data.get("extends") or data.get("extends") or []
    extends = [str(x) for x in extends_raw]

    overrides = data.get("overrides", {})
    if not isinstance(overrides, dict):
        overrides = {}

    slices_raw = data.get("vertical_slices", {}).get("slices") or data.get("slices") or []
    slices: list[SliceConfig] = []
    for s in slices_raw:
        if isinstance(s, dict):
            slices.append(
                SliceConfig(
                    type=str(s.get("type", "feature")),
                    name=str(s.get("name", "")),
                    prefix=str(s.get("prefix", "")),
                    requires_adr=bool(s.get("requires_adr", False)),
                    description=str(s.get("description", "")),
                )
            )

    invariants_data = data.get("invariants", {})
    invariants: list[str] = []
    if isinstance(invariants_data, dict):
        invariants = [str(r) for r in invariants_data.get("rules", [])]
    elif isinstance(invariants_data, list):
        invariants = [str(r) for r in invariants_data]

    # ADRs from directory if base_dir exists
    adrs: list[BaselineADR] = []
    if base_dir and base_dir.is_dir():
        adr_candidates: list[Path] = []
        for cand_dir in [
            base_dir / "adrs" / "accepted",
            base_dir / "adrs",
            base_dir / "docs" / "project" / "adrs" / "accepted",
            base_dir,
        ]:
            if cand_dir.is_dir():
                for f in sorted(cand_dir.glob("*.md")):
                    if f.name.startswith("adr-") or (cand_dir.name in ("adrs", "accepted") and f.name.endswith(".md")):
                        if f not in adr_candidates:
                            adr_candidates.append(f)
        for adr_path in adr_candidates:
            try:
                txt = adr_path.read_text(encoding="utf-8")
                adrs.append(parse_adr_content(txt, filename=adr_path.name))
            except OSError:
                pass

    return Profile(
        id=p_id,
        name=name,
        description=description,
        version=version,
        extends=extends,
        adrs=adrs,
        slices=slices,
        overrides=overrides,
        invariants=invariants,
    )


def load_profile_definition(identifier_or_path: str | Path, base_dir: Path | None = None) -> Profile:
    """Loads a profile definition from built-in registry, filesystem path, or bundle."""
    path = Path(identifier_or_path)
    if not path.is_absolute() and base_dir:
        candidate = base_dir / path
        if candidate.exists():
            path = candidate

    if not path.exists():
        # Check profiles/<name> or base_dir/profiles/<name>
        prefixes = [base_dir] if base_dir else []
        prefixes.append(Path("."))
        for prefix in prefixes:
            for cand in [
                prefix / "profiles" / identifier_or_path,
                prefix / "profiles" / str(identifier_or_path).replace("@", "-"),
                prefix / "profiles" / f"{identifier_or_path}-profile",
                prefix / "upstream" / identifier_or_path,
            ]:
                if cand.exists():
                    path = cand
                    break
            if path.exists():
                break

    if path.is_file():
        if path.name.endswith((".tar.gz", ".sop", ".tar")):
            from .packager import load_profile_from_bundle
            return load_profile_from_bundle(path)
        elif path.name.endswith(".toml"):
            toml_text = path.read_text(encoding="utf-8")
            return parse_profile_toml(toml_text, base_dir=path.parent)

    if path.is_dir():
        toml_path = path / "profile.toml"
        if toml_path.is_file():
            toml_text = toml_path.read_text(encoding="utf-8")
            return parse_profile_toml(toml_text, base_dir=path)
        else:
            # Profile dir without profile.toml: assemble from directory ADRs
            adrs: list[BaselineADR] = []
            for f in sorted(path.glob("*.md")):
                try:
                    adrs.append(parse_adr_content(f.read_text(encoding="utf-8"), filename=f.name))
                except OSError:
                    pass
            return Profile(id=path.name, name=path.name, description="", adrs=adrs)

    # Check built-in and release registry
    if isinstance(identifier_or_path, str):
        reg_p = get_profile(identifier_or_path)
        if reg_p is not None:
            return reg_p

    raise ProfileError(f"Unknown profile: '{identifier_or_path}'")
# pragma: no mutate end


def resolve_inheritance_dag(
    root: Profile,
    loader: Callable[[str], Profile] = load_profile_definition,
) -> list[Profile]:
    """Resolves profile inheritance DAG in topological order, detecting circular dependencies."""
    visiting: list[str] = []
    visited: set[str] = set()
    ordered: list[Profile] = []

    def dfs(current: Profile) -> None:
        cid = current.id
        if cid in visiting:
            cycle_idx = visiting.index(cid)
            cycle_nodes = visiting[cycle_idx:] + [cid]
            cycle_str = " -> ".join(cycle_nodes)
            raise ProfileInheritanceError(
                f"Profile Inheritance Error: Circular dependency detected ({cycle_str})"
            )
        if cid in visited:
            return

        visiting.append(cid)
        for parent_id in current.extends:
            parent_profile = loader(parent_id)
            dfs(parent_profile)

        visiting.pop()
        visited.add(cid)
        ordered.append(current)

    dfs(root)
    return ordered


def merge_overrides(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """Deep merges override dictionary into base dictionary."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = merge_overrides(result[k], v)
        else:
            result[k] = v
    return result


def compose_profiles(
    profiles_input: list[str | Profile | Path],
    loader: Callable[[str], Profile] = load_profile_definition,
) -> ResolvedComposition:
    """Composes multiple profiles, validating inheritance, collisions, and overrides."""
    if not profiles_input:
        return ResolvedComposition(profile_ids=[], adrs=[])

    all_ordered_profiles: list[Profile] = []
    seen_profile_ids: set[str] = set()

    for item in profiles_input:
        root_prof = item if isinstance(item, Profile) else loader(str(item))
        chain = resolve_inheritance_dag(root_prof, loader=loader)
        for p in chain:
            if p.id not in seen_profile_ids:
                seen_profile_ids.add(p.id)
                all_ordered_profiles.append(p)

    # Determine highest ADR number across all profiles upfront for suggestions
    max_adr_num = 0
    for p in all_ordered_profiles:
        for adr in p.adrs:
            if adr.number > max_adr_num:
                max_adr_num = adr.number

    merged_adrs: list[BaselineADR] = []
    seen_numbers: dict[int, tuple[str, BaselineADR]] = {}
    seen_slugs: dict[str, BaselineADR] = {}

    for p in all_ordered_profiles:
        for adr in p.adrs:
            if adr.slug in seen_slugs:
                continue

            if adr.number in seen_numbers:
                existing_pid, existing_adr = seen_numbers[adr.number]
                if existing_adr.slug != adr.slug or existing_adr.title != adr.title:
                    next_avail = max_adr_num + 1
                    msg = (
                        f"Profile Error: Conflict detected for {adr.canonical_id} between "
                        f"'{existing_pid}' and '{p.id}'. Suggest next available number ADR-{next_avail:04d}."
                    )
                    raise ADRCollisionError(msg)

            seen_numbers[adr.number] = (p.id, adr)
            seen_slugs[adr.slug] = adr
            merged_adrs.append(adr)

    merged_overrides: dict[str, Any] = {}
    for p in all_ordered_profiles:
        merged_overrides = merge_overrides(merged_overrides, p.overrides)

    slices_by_type: dict[str, SliceConfig] = {}
    for p in all_ordered_profiles:
        for s in p.slices:
            slices_by_type[s.type] = s

    invariants_set: list[str] = []
    for p in all_ordered_profiles:
        for inv in p.invariants:
            if inv not in invariants_set:
                invariants_set.append(inv)

    file_limit = 500
    arch_overrides = merged_overrides.get("architecture", {})
    if isinstance(arch_overrides, dict) and "file_length_limit" in arch_overrides:
        try:
            file_limit = int(arch_overrides["file_length_limit"])
        except (ValueError, TypeError):
            pass

    latest_version = all_ordered_profiles[-1].version if all_ordered_profiles else "0.1.0"

    return ResolvedComposition(
        profile_ids=[p.id for p in all_ordered_profiles],
        adrs=merged_adrs,
        overrides=merged_overrides,
        slices=list(slices_by_type.values()),
        invariants=invariants_set,
        version=latest_version,
        file_length_limit=file_limit,
    )
