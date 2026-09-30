"""Packaging, distribution, and installation of modular architectural profiles."""

from __future__ import annotations

import io
import re
import sys
import tarfile
from pathlib import Path
from typing import Any

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore

from .composer import compose_profiles, parse_adr_content, parse_profile_toml
from .models import BaselineADR, Profile, ProfileError
from .registry import PROFILES, get_profile


def validate_profile_source(profile_dir: Path) -> tuple[bool, list[str]]:
    """Validates profile manifest, ADR frontmatter, custom file limits, and agent rule fragments."""
    errors: list[str] = []
    toml_path = profile_dir / "profile.toml"
    if not toml_path.is_file():
        errors.append("Missing 'profile.toml' manifest in profile directory")
        return False, errors

    try:
        data = tomllib.loads(toml_path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"Invalid TOML in profile.toml: {exc}")
        return False, errors

    prof_data = data.get("profile", {})
    p_id = prof_data.get("id") or data.get("id")
    if not p_id:
        errors.append("Profile manifest must declare an 'id'")

    # Validate custom file limits if declared
    overrides = data.get("overrides", {})
    if isinstance(overrides, dict):
        arch_ov = overrides.get("architecture", {})
        if isinstance(arch_ov, dict) and "file_length_limit" in arch_ov:
            f_lim = arch_ov["file_length_limit"]
            if not isinstance(f_lim, int) or f_lim <= 0:
                errors.append(f"Invalid architecture file_length_limit: {f_lim} (must be positive integer)")

    # Validate agent rule fragments / invariants
    inv_data = data.get("invariants", {})
    rules = []
    if isinstance(inv_data, dict):
        rules = inv_data.get("rules", [])
    elif isinstance(inv_data, list):
        rules = inv_data
    for r in rules:
        if not isinstance(r, str) or not r.strip():
            errors.append("Invariant rules must be non-empty strings")

    # Validate ADR frontmatter & headers
    adr_candidates: list[Path] = []
    for cand_dir in [profile_dir / "adrs" / "accepted", profile_dir / "adrs", profile_dir]:
        if cand_dir.is_dir():
            for f in sorted(cand_dir.glob("*.md")):
                if f.name.startswith("adr-") or cand_dir.name in ("adrs", "accepted"):
                    if f not in adr_candidates:
                        adr_candidates.append(f)

    for adr_path in adr_candidates:
        content = adr_path.read_text(encoding="utf-8")
        adr = parse_adr_content(content, filename=adr_path.name)
        if not adr.title:
            errors.append(f"ADR {adr_path.name} missing title in frontmatter or header")
        if adr.number < 0:
            errors.append(f"ADR {adr_path.name} has invalid negative ADR number: {adr.number}")

    return len(errors) == 0, errors


def package_profile(source: str | Path, output_path: str | Path) -> Path:
    """Packages a profile directory or registered profile into a validated .sop or .tar.gz bundle."""
    out = Path(output_path).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    src_path = Path(source)
    if not src_path.exists():
        for cand in [Path("profiles") / source, Path("profiles") / f"{source}-profile"]:
            if cand.exists():
                src_path = cand
                break

    if src_path.is_dir():
        is_valid, errors = validate_profile_source(src_path)
        if not is_valid:
            raise ProfileError(f"Profile packaging validation failed: {'; '.join(errors)}")

        with tarfile.open(out, "w:gz") as tar:
            for item in sorted(src_path.rglob("*")):
                if item.is_file() and not item.name.startswith("."):
                    rel_name = item.relative_to(src_path).as_posix()
                    tar.add(item, arcname=rel_name)
        return out

    # Check if registered built-in profile (e.g. 'fintech', 'security')
    lowered = str(source).lower()
    if lowered in PROFILES:
        prof = PROFILES[lowered]
        with tarfile.open(out, "w:gz") as tar:
            # Generate profile.toml
            toml_content = (
                f'[profile]\nid = "{prof.id}"\nname = "{prof.name}"\n'
                f'version = "{prof.version}"\ndescription = "{prof.description}"\n'
            )
            toml_bytes = toml_content.encode("utf-8")
            ti = tarfile.TarInfo(name="profile.toml")
            ti.size = len(toml_bytes)
            tar.addfile(ti, io.BytesIO(toml_bytes))

            # Add ADRs
            for adr in prof.adrs:
                adr_bytes = adr.content.encode("utf-8")
                ati = tarfile.TarInfo(name=f"adrs/{adr.filename}")
                ati.size = len(adr_bytes)
                tar.addfile(ati, io.BytesIO(adr_bytes))
        return out

    raise ProfileError(f"Cannot package unknown profile source: '{source}'")


def load_profile_from_bundle(bundle_path: str | Path) -> Profile:
    """Loads a Profile instance from an archived .sop or .tar.gz bundle."""
    b_path = Path(bundle_path).resolve()
    if not b_path.is_file():
        raise ProfileError(f"Profile bundle not found: {b_path}")

    toml_content: str | None = None
    adrs: list[BaselineADR] = []

    with tarfile.open(b_path, "r:*") as tar:
        for member in tar.getmembers():
            if not member.isfile():
                continue
            name = member.name.lstrip("./")
            if name == "profile.toml" or name.endswith("/profile.toml"):
                f = tar.extractfile(member)
                if f:
                    toml_content = f.read().decode("utf-8")
            elif name.endswith(".md"):
                f = tar.extractfile(member)
                if f:
                    txt = f.read().decode("utf-8")
                    base_name = Path(name).name
                    adrs.append(parse_adr_content(txt, filename=base_name))

    if not toml_content:
        raise ProfileError(f"Bundle {b_path.name} does not contain profile.toml")

    prof = parse_profile_toml(toml_content)
    if adrs and not prof.adrs:
        prof.adrs = adrs
    return prof


def install_profile_bundle(bundle_path_or_id: str | Path, target_dir: Path) -> Profile:
    """Installs a profile bundle into an existing target repository."""
    target_root = target_dir.resolve()
    prof = load_profile_from_bundle(bundle_path_or_id) if Path(bundle_path_or_id).is_file() else get_profile(str(bundle_path_or_id))
    if not prof:
        from .composer import load_profile_definition
        prof = load_profile_definition(bundle_path_or_id, base_dir=target_root)

    composition = compose_profiles([prof])

    # Install ADRs to docs/project/adrs/accepted/
    adrs_dir = target_root / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)
    registry_file = target_root / "docs" / "project" / "adrs" / "REGISTRY.md"

    highest_num = 0
    for p in list(adrs_dir.glob("*.md")):
        m = re.match(r"^adr-(\d+)", p.name)
        if m:
            highest_num = max(highest_num, int(m.group(1)))

    existing_slugs = {p.stem for p in adrs_dir.glob("*.md")}
    new_registry_rows: list[str] = []

    for adr in composition.adrs:
        if any(adr.slug in s for s in existing_slugs):
            continue
        highest_num = max(highest_num + 1, adr.number)
        filename = f"adr-{highest_num:04d}-{adr.slug}.md"
        old_id = f"ADR-{adr.number:04d}"
        new_id = f"ADR-{highest_num:04d}"
        content = adr.content.replace(old_id, new_id) if adr.content else f"# {new_id}: {adr.title}\n\n## Status\n{adr.status}\n"
        adr_file = adrs_dir / filename
        adr_file.write_text(content.strip() + "\n", encoding="utf-8")
        new_registry_rows.append(f"| {new_id} | {adr.title} | {adr.status} | {adr.date} |")

    if registry_file.is_file() and new_registry_rows:
        reg_text = registry_file.read_text(encoding="utf-8")
        reg_text = reg_text.rstrip() + "\n" + "\n".join(new_registry_rows) + "\n"
        registry_file.write_text(reg_text, encoding="utf-8")

    # Update specops.toml
    toml_path = target_root / "specops.toml"
    if toml_path.is_file():
        text = toml_path.read_text(encoding="utf-8")
        # Apply architecture file_length_limit if overridden
        if composition.file_length_limit != 500:
            text = re.sub(r"file_length_limit\s*=\s*\d+", f"file_length_limit = {composition.file_length_limit}", text)
        # Apply quality overrides
        qual_overrides = composition.overrides.get("quality", {})
        if qual_overrides.get("require_mutation_testing"):
            if "require_mutation_testing" not in text:
                text = text.replace("[quality]", "[quality]\nrequire_mutation_testing = true")

        # Record installed profile and version
        if "[profiles]" in text:
            m = re.search(r"installed\s*=\s*\[(.*?)\]", text)
            if m:
                existing_raw = m.group(1)
                existing_items = [x.strip().strip("'\"") for x in existing_raw.split(",") if x.strip()]
                for pid in composition.profile_ids:
                    if pid not in existing_items:
                        existing_items.append(pid)
                new_fmt = ", ".join(f'"{x}"' for x in existing_items)
                text = text[:m.start()] + f"installed = [{new_fmt}]" + text[m.end():]
            text = re.sub(r'version\s*=\s*"[^"]*"', f'version = "{composition.version}"', text)
        else:
            prof_ids_fmt = ", ".join(f'"{pid}"' for pid in composition.profile_ids)
            text += f'\n[profiles]\ninstalled = [{prof_ids_fmt}]\nversion = "{composition.version}"\n'
        toml_path.write_text(text, encoding="utf-8")

    # Update AGENTS.md
    agents_path = target_root / "AGENTS.md"
    if agents_path.is_file():
        a_text = agents_path.read_text(encoding="utf-8")
        if composition.file_length_limit != 500:
            a_text = re.sub(
                r"1\.\s*\*\*File Length Limit \(<\d+ lines\)\*\*:",
                f"1. **File Length Limit (<{composition.file_length_limit} lines)**:",
                a_text,
            )
            a_text = re.sub(
                r"Source files over ~\d+ lines",
                f"Source files over ~{composition.file_length_limit} lines",
                a_text,
            )
        if composition.invariants:
            inv_lines = "\n".join(f"- {inv}" for inv in composition.invariants if inv not in a_text)
            if inv_lines:
                a_text += f"\n\n## Custom Profile Invariants ({prof.name})\n{inv_lines}\n"
        agents_path.write_text(a_text, encoding="utf-8")

    return prof
