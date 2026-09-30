"""Living Constitution synchronization, custom extension preservation, and CI drift detection."""

from __future__ import annotations

import difflib
import subprocess
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..profiles.models import ADRDefinition

BEGIN_CUSTOM_INVARIANTS = "<!-- BEGIN CUSTOM INVARIANTS -->"
END_CUSTOM_INVARIANTS = "<!-- END CUSTOM INVARIANTS -->"


def extract_custom_invariants(content: str) -> str | None:
    """Extracts text enclosed within custom invariants comment delimiters."""
    start_idx = content.find(BEGIN_CUSTOM_INVARIANTS)
    if start_idx == -1:
        return None
    content_after_start = content[start_idx + len(BEGIN_CUSTOM_INVARIANTS):]
    end_idx = content_after_start.find(END_CUSTOM_INVARIANTS)
    if end_idx == -1:
        return None
    return content_after_start[:end_idx]


def wrap_custom_invariants(custom_text: str | None) -> str:
    """Wraps custom invariants text with comment delimiters."""
    if custom_text is None:
        return f"{BEGIN_CUSTOM_INVARIANTS}\n{END_CUSTOM_INVARIANTS}"
    return f"{BEGIN_CUSTOM_INVARIANTS}{custom_text}{END_CUSTOM_INVARIANTS}"


def inject_custom_invariants(content: str, custom_text: str | None) -> str:
    """Injects or replaces custom invariants block in constitution content."""
    wrapped = wrap_custom_invariants(custom_text)
    start_idx = content.find(BEGIN_CUSTOM_INVARIANTS)
    if start_idx != -1:
        end_idx = content.find(END_CUSTOM_INVARIANTS, start_idx + len(BEGIN_CUSTOM_INVARIANTS))
        if end_idx != -1:
            before = content[:start_idx]
            after = content[end_idx + len(END_CUSTOM_INVARIANTS):]
            return f"{before}{wrapped}{after}"

    marker = "## Design Principles"
    if marker in content:
        parts = content.split(marker, 1)
        return f"{parts[0]}{wrapped}\n\n---\n\n{marker}{parts[1]}"
    return f"{content.rstrip()}\n\n{wrapped}\n"


def generate_expected_constitution(
    root_dir: Path,
    custom_text: str | None = None,
) -> str:
    """Generates the authoritative constitution text based on root_dir configuration."""
    from ..config.loader import load_config
    from ..profiles.registry import resolve_adrs_for_profiles
    from .agents_md import generate_agents_md

    cfg = load_config(root_dir=root_dir)
    profiles = ["core", "bdd", "ddd"]

    if cfg.security is not None:
        if "security" not in profiles:
            profiles.append("security")
    else:
        sec_md = root_dir / "docs" / "project" / "SECURITY.md"
        toml_path = root_dir / "specops.toml"
        if sec_md.exists() or (toml_path.exists() and "[security]" in toml_path.read_text(encoding="utf-8")):
            if "security" not in profiles:
                profiles.append("security")

    adrs_dir = root_dir / "docs" / "project" / "adrs"
    superseded_map: dict[str, str] = {}
    try:
        from ..adrs.supersede import discover_superseded_adrs
        superseded_map = discover_superseded_adrs(adrs_dir)
    except Exception:
        pass

    adrs = resolve_adrs_for_profiles(profiles)
    return generate_agents_md(
        cfg.project.name,
        profiles,
        adrs,
        file_length_limit=cfg.architecture.file_length_limit,
        root_dir=root_dir,
        superseded_map=superseded_map,
        preflight_commands=cfg.quality.preflight,
        custom_invariants_text=custom_text,
    )


def sync_constitution(root_dir: Path) -> tuple[bool, str]:
    """Synchronizes AGENTS.md and docs/operating-manual.md while preserving custom sections."""
    agents_path = root_dir / "AGENTS.md"
    existing_content = agents_path.read_text(encoding="utf-8") if agents_path.exists() else ""
    custom_text = extract_custom_invariants(existing_content)

    new_content = generate_expected_constitution(root_dir, custom_text=custom_text)
    agents_path.write_text(new_content, encoding="utf-8")

    from ..docs.builder import sync_operating_manual
    sync_operating_manual(root_dir, root_dir / "docs")

    adrs_dir = root_dir / "docs" / "project" / "adrs"
    superseded_map: dict[str, str] = {}
    try:
        from ..adrs.supersede import discover_superseded_adrs
        superseded_map = discover_superseded_adrs(adrs_dir)
    except Exception:
        pass

    if (root_dir / ".git").exists() and superseded_map and new_content != existing_content:
        trailers = [f"SpecOps-ADR: {new_id}" for new_id in sorted(set(superseded_map.values()))]
        trailer_str = "\n".join(trailers)
        commit_msg = f"docs: re-synchronize AGENTS.md constitution\n\n{trailer_str}"
        try:
            subprocess.run(["git", "add", "AGENTS.md"], cwd=root_dir, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-m", commit_msg], cwd=root_dir, check=True, capture_output=True)
        except Exception:
            pass

    return True, "AGENTS.md and docs/operating-manual.md updated successfully with active profile invariants."


def check_constitution(root_dir: Path) -> tuple[bool, str, str]:
    """Checks for drift between specops.toml settings and root AGENTS.md.

    Returns:
        (in_sync, diff_diagnostics, message)
    """
    agents_path = root_dir / "AGENTS.md"
    if not agents_path.exists():
        diff = "AGENTS.md does not exist."
        msg = "Constitution Drift Error: AGENTS.md is out of sync with specops.toml. Run 'spec-ops scaffold agents' to update."
        return False, diff, msg

    existing_content = agents_path.read_text(encoding="utf-8")
    custom_text = extract_custom_invariants(existing_content)
    expected_content = generate_expected_constitution(root_dir, custom_text=custom_text)

    if existing_content.strip() == expected_content.strip():
        return True, "", "✅ AGENTS.md is synchronized with configuration."

    diff_lines = list(
        difflib.unified_diff(
            existing_content.splitlines(keepends=True),
            expected_content.splitlines(keepends=True),
            fromfile="AGENTS.md (actual)",
            tofile="AGENTS.md (expected)",
        )
    )
    diff_diagnostics = "".join(diff_lines)
    msg = "Constitution Drift Error: AGENTS.md is out of sync with specops.toml. Run 'spec-ops scaffold agents' to update."
    return False, diff_diagnostics, msg
