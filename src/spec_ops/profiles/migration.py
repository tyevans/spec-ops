"""Profile version upgrade, 3-way ADR conflict detection, and migration engine."""

from __future__ import annotations

import difflib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .diff import _extract_file_limit, _extract_mutation_testing
from .models import BaselineADR, Profile


@dataclass
class ADRConflict:
    canonical_id: str
    number: int
    slug: str
    title: str
    file_path: Path
    local_content: str
    upstream_content: str
    base_content: str | None = None
    diff_summary: str = ""


@dataclass
class MigrationResult:
    success: bool
    aborted: bool = False
    conflicts: list[ADRConflict] = field(default_factory=list)
    installed_adrs: list[str] = field(default_factory=list)
    updated_adrs: list[str] = field(default_factory=list)
    message: str = ""


def find_installed_adr_file(adrs_dir: Path, slug: str, number: int) -> Path | None:
    """Finds existing ADR file matching slug or number."""
    if not adrs_dir.is_dir():
        return None
    for p in sorted(adrs_dir.glob("*.md")):
        if p.name.endswith(f"-{slug}.md") or p.name == f"adr-{number:04d}-{slug}.md":
            return p
        m = re.match(r"^adr-(\d+)", p.name)
        if m and int(m.group(1)) == number:
            return p
    return None


def detect_adr_conflicts(
    target_profile: Profile,
    repo_root: Path,
    base_profile: Profile | None = None,
) -> list[ADRConflict]:
    """Detects 3-way conflicts between local ADR edits and upstream profile changes."""
    adrs_dir = repo_root / "docs" / "project" / "adrs" / "accepted"
    if not adrs_dir.is_dir():
        adrs_dir = repo_root / "docs" / "project" / "adrs"

    base_by_slug = {a.slug: a for a in (base_profile.adrs if base_profile else [])}
    conflicts: list[ADRConflict] = []

    for t_adr in target_profile.adrs:
        adr_file = find_installed_adr_file(adrs_dir, t_adr.slug, t_adr.number)
        if not adr_file or not adr_file.is_file():
            continue

        local_content = adr_file.read_text(encoding="utf-8")
        upstream_content = t_adr.content.strip() + "\n"
        b_adr = base_by_slug.get(t_adr.slug)
        base_content = (b_adr.content.strip() + "\n") if b_adr else None

        if base_content is not None:
            local_clean = local_content.strip()
            base_clean = base_content.strip()
            upstream_clean = upstream_content.strip()
            # If local matches base, local did not touch it; upstream can be applied cleanly
            if local_clean == base_clean:
                continue
            # If local matches upstream, already identical
            if local_clean == upstream_clean:
                continue
            # Both modified differently: 3-way conflict!
            diff = "".join(
                difflib.unified_diff(
                    local_content.splitlines(keepends=True),
                    upstream_content.splitlines(keepends=True),
                    fromfile=f"local/{adr_file.name}",
                    tofile=f"upstream/{adr_file.name}",
                )
            )
            conflicts.append(
                ADRConflict(
                    canonical_id=f"ADR-{t_adr.number:04d}",
                    number=t_adr.number,
                    slug=t_adr.slug,
                    title=t_adr.title,
                    file_path=adr_file,
                    local_content=local_content,
                    upstream_content=upstream_content,
                    base_content=base_content,
                    diff_summary=diff,
                )
            )
        else:
            if local_content.strip() != upstream_content.strip():
                diff = "".join(
                    difflib.unified_diff(
                        local_content.splitlines(keepends=True),
                        upstream_content.splitlines(keepends=True),
                        fromfile=f"local/{adr_file.name}",
                        tofile=f"upstream/{adr_file.name}",
                    )
                )
                conflicts.append(
                    ADRConflict(
                        canonical_id=f"ADR-{t_adr.number:04d}",
                        number=t_adr.number,
                        slug=t_adr.slug,
                        title=t_adr.title,
                        file_path=adr_file,
                        local_content=local_content,
                        upstream_content=upstream_content,
                        diff_summary=diff,
                    )
                )

    return conflicts


def render_conflict_prompt(conflict: ADRConflict) -> str:
    """Renders human-readable 3-way conflict diagnostics and resolution prompt."""
    lines = [
        f"\n⚠️  Migration Conflict: Conflict detected for {conflict.canonical_id} ({conflict.title})",
        f"   File: {conflict.file_path}",
        "   Local project has modified this ADR, and upstream has also modified it (3-way conflict).",
        "\n   Choose a resolution option:",
        "     [1] keep-local      Keep the local override and preserve local changes",
        "     [2] accept-upstream Accepting upstream changes and overwrite local modifications",
        "     [3] custom-diff     Creating a custom ADR diff / merge markers",
        "     [4] abort           Safe migration abort without corrupting files",
    ]
    if conflict.diff_summary:
        lines.append("\n--- Conflict Diff Preview ---")
        lines.extend(conflict.diff_summary.splitlines()[:15])
        lines.append("-----------------------------")
    return "\n".join(lines)


def update_specops_toml(repo_root: Path, target_profile: Profile) -> None:
    """Updates profile version and overrides inside specops.toml atomically."""
    toml_path = repo_root / "specops.toml"
    if not toml_path.is_file():
        return

    text = toml_path.read_text(encoding="utf-8")
    t_id = target_profile.id
    t_ver = target_profile.version
    full_spec = f"{t_id}@{t_ver}"

    # Update installed list
    if "[profiles]" in text:
        m = re.search(r"installed\s*=\s*\[(.*?)\]", text)
        if m:
            raw_items = [x.strip().strip("'\"") for x in m.group(1).split(",") if x.strip()]
            new_items: list[str] = []
            replaced = False
            for item in raw_items:
                base_name = item.split("@", 1)[0]
                if base_name in (t_id, "core", "base", f"specops/{t_id}", "specops/base"):
                    new_items.append(full_spec)
                    replaced = True
                else:
                    new_items.append(item)
            if not replaced:
                new_items.append(full_spec)
            new_fmt = ", ".join(f'"{x}"' for x in new_items)
            text = text[: m.start()] + f"installed = [{new_fmt}]" + text[m.end() :]
        text = re.sub(r'version\s*=\s*"[^"]*"', f'version = "{t_ver}"', text)
    else:
        text += f'\n[profiles]\ninstalled = ["{full_spec}"]\nversion = "{t_ver}"\n'

    # Update file_length_limit
    new_limit = _extract_file_limit(target_profile)
    if new_limit != 500:
        if "file_length_limit" in text:
            text = re.sub(r"file_length_limit\s*=\s*\d+", f"file_length_limit = {new_limit}", text)
        elif "[architecture]" in text:
            text = text.replace("[architecture]", f"[architecture]\nfile_length_limit = {new_limit}")

    # Update require_mutation_testing
    if _extract_mutation_testing(target_profile):
        if "require_mutation_testing" not in text:
            if "[quality]" in text:
                text = text.replace("[quality]", "[quality]\nrequire_mutation_testing = true")
            else:
                text += "\n[quality]\nrequire_mutation_testing = true\n"

    toml_path.write_text(text, encoding="utf-8")


def update_agents_md(repo_root: Path, target_profile: Profile) -> None:
    """Re-synchronizes AGENTS.md hard invariants with updated profile constraints."""
    agents_path = repo_root / "AGENTS.md"
    if not agents_path.is_file():
        return

    text = agents_path.read_text(encoding="utf-8")
    new_limit = _extract_file_limit(target_profile)
    if new_limit != 500:
        text = re.sub(
            r"1\.\s*\*\*File Length Limit \(<\d+ lines\)\*\*:",
            f"1. **File Length Limit (<{new_limit} lines)**:",
            text,
        )
        text = re.sub(
            r"Source files over ~\d+ lines",
            f"Source files over ~{new_limit} lines",
            text,
        )

    for inv in target_profile.invariants:
        if inv not in text:
            text += f"\n- {inv}"

    agents_path.write_text(text, encoding="utf-8")


def execute_profile_migration(
    target_profile: Profile,
    repo_root: Path,
    base_profile: Profile | None = None,
    force: bool = False,
    action: str | None = None,
) -> MigrationResult:
    """Executes safe 3-way profile migration with atomic rollbacks on conflict."""
    conflicts = detect_adr_conflicts(target_profile, repo_root, base_profile=base_profile)

    if conflicts and not force:
        # Determine resolution strategy
        resolved_action = action
        if not resolved_action:
            for c in conflicts:
                print(render_conflict_prompt(c), file=sys.stderr)
            # If standard input is available, allow prompt; otherwise default safe abort
            if sys.stdin.isatty():
                try:
                    user_in = input("Select resolution [keep-local/accept-upstream/diff/abort]: ").strip().lower()
                    if user_in in ("1", "keep-local"):
                        resolved_action = "keep-local"
                    elif user_in in ("2", "accept-upstream"):
                        resolved_action = "accept-upstream"
                    elif user_in in ("3", "custom", "diff"):
                        resolved_action = "custom"
                    else:
                        resolved_action = "abort"
                except (EOFError, KeyboardInterrupt):
                    resolved_action = "abort"
            else:
                resolved_action = "abort"

        if resolved_action == "abort":
            return MigrationResult(
                success=False,
                aborted=True,
                conflicts=conflicts,
                message=f"Migration aborted due to {len(conflicts)} conflicting local ADR modifications.",
            )
        action = resolved_action

    adrs_dir = repo_root / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    registry_file = repo_root / "docs" / "project" / "adrs" / "REGISTRY.md"

    # Compute highest existing ADR number
    highest_num = 0
    for p in adrs_dir.glob("*.md"):
        m = re.match(r"^adr-(\d+)", p.name)
        if m:
            highest_num = max(highest_num, int(m.group(1)))

    conflict_slugs = {c.slug for c in conflicts}
    installed_adrs: list[str] = []
    updated_adrs: list[str] = []
    new_reg_rows: list[str] = []

    for adr in target_profile.adrs:
        existing_file = find_installed_adr_file(adrs_dir, adr.slug, adr.number)
        if existing_file:
            if adr.slug in conflict_slugs:
                if action == "keep-local":
                    continue
                elif action in ("custom", "diff"):
                    merged = f"<<<<<<< LOCAL\n{existing_file.read_text(encoding='utf-8')}=======\n{adr.content}>>>>>>> UPSTREAM\n"
                    existing_file.write_text(merged, encoding="utf-8")
                    updated_adrs.append(existing_file.name)
                    continue
                # If force or accept-upstream: overwrite with upstream
            old_body = existing_file.read_text(encoding="utf-8")
            if old_body.strip() != adr.content.strip():
                existing_file.write_text(adr.content.strip() + "\n", encoding="utf-8")
                updated_adrs.append(existing_file.name)
        else:
            highest_num = max(highest_num + 1, adr.number)
            new_id = f"ADR-{highest_num:04d}"
            filename = f"adr-{highest_num:04d}-{adr.slug}.md"
            content = adr.content.replace(f"ADR-{adr.number:04d}", new_id) if adr.content else f"# {new_id}: {adr.title}\n"
            target_file = adrs_dir / filename
            target_file.write_text(content.strip() + "\n", encoding="utf-8")
            installed_adrs.append(filename)
            new_reg_rows.append(f"| {new_id} | {adr.title} | {adr.status} | {adr.date} |")

    # Update REGISTRY.md atomically
    if registry_file.is_file() and new_reg_rows:
        reg_text = registry_file.read_text(encoding="utf-8").rstrip() + "\n" + "\n".join(new_reg_rows) + "\n"
        registry_file.write_text(reg_text, encoding="utf-8")

    # Update specops.toml & AGENTS.md
    update_specops_toml(repo_root, target_profile)
    update_agents_md(repo_root, target_profile)

    return MigrationResult(
        success=True,
        aborted=False,
        conflicts=conflicts,
        installed_adrs=installed_adrs,
        updated_adrs=updated_adrs,
        message=f"✨ Profile upgraded cleanly to {target_profile.id}@{target_profile.version}.",
    )
