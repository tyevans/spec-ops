"""Handler for spec-ops profile CLI commands."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ..profiles.models import ProfileError


def handle_profile_command(args: Any, config: Any) -> int:
    """Dispatches profile actions: apply, sync, info, list, package, export, install, validate, inspect."""
    action = getattr(args, "profile_action", None)

    if action == "apply":
        p_name = args.profile_name.lower()
        if p_name == "security":
            from ..profiles.security import apply_security_profile

            apply_security_profile(config.root_dir)
            print(f"✨ Applied '{p_name}' architectural profile to repository.")
            return 0
        else:
            try:
                from ..profiles.packager import install_profile_bundle
                install_profile_bundle(args.profile_name, config.root_dir)
                print(f"✨ Applied '{p_name}' architectural profile to repository.")
                return 0
            except ProfileError as err:
                print(f"❌ {err}", file=sys.stderr)
                return 1

    elif action == "sync":
        p_name = args.profile_name.lower()
        if p_name == "security":
            from ..profiles.security import sync_security_profile

            sync_security_profile(config.root_dir)
            print(f"✅ Synchronized '{p_name}' architectural profile.")
            return 0
        else:
            print(f"❌ Unknown profile: {p_name}", file=sys.stderr)
            return 1

    elif action in ("package", "export"):
        from ..profiles.packager import package_profile

        try:
            out_file = package_profile(args.source, args.output)
            print(f"✨ Profile bundle created: {out_file}")
            return 0
        except ProfileError as err:
            print(f"❌ {err}", file=sys.stderr)
            return 1

    elif action == "install":
        from ..profiles.packager import install_profile_bundle

        try:
            prof = install_profile_bundle(args.bundle, config.root_dir)
            print(f"✨ Installed profile '{prof.id}' from {args.bundle}")
            return 0
        except ProfileError as err:
            print(f"❌ {err}", file=sys.stderr)
            return 1

    elif action == "validate":
        from ..profiles.composer import load_profile_definition, resolve_inheritance_dag

        try:
            p = load_profile_definition(args.profile_target)
            chain = resolve_inheritance_dag(p)
            print(f"✨ Profile '{p.id}' validated successfully.")
            print(f"📦 Inherited Profiles: {', '.join(x.id for x in chain)}")
            return 0
        except ProfileError as err:
            print(f"{err}", file=sys.stderr)
            return 1

    elif action == "inspect":
        from ..profiles.composer import compose_profiles, load_profile_definition

        target = args.profile_target
        if target == "." or not target:
            toml_file = config.root_dir / "specops.toml"
            if toml_file.is_file():
                try:
                    import tomllib
                    t_data = tomllib.loads(toml_file.read_text(encoding="utf-8"))
                    installed = t_data.get("profiles", {}).get("installed", [])
                    if installed:
                        target = installed[0]
                    else:
                        p_dir = config.root_dir / "profiles"
                        if p_dir.is_dir():
                            subdirs = [d for d in p_dir.iterdir() if d.is_dir()]
                            target = str(subdirs[0]) if subdirs else "core"
                        else:
                            target = "core"
                except Exception:
                    target = "core"
            else:
                target = "core"

        try:
            comp = compose_profiles([target])
            prof_name = comp.profile_ids[-1] if comp.profile_ids else target
            print(f"=== SpecOps Profile Inspection: {prof_name} ===")
            print(f"Inherited Profiles: {', '.join(comp.profile_ids)}")
            print("Baseline ADRs:")
            for adr in comp.adrs:
                print(f"  • {adr.canonical_id}: {adr.title}")
            print(f"File Length Limit: {comp.file_length_limit}")
            if comp.slices:
                print(f"Vertical Slices: {', '.join(s.type for s in comp.slices)}")
            if comp.invariants:
                print(f"Invariants: {len(comp.invariants)} rules")
            return 0
        except ProfileError as err:
            print(f"{err}", file=sys.stderr)
            return 1

    elif action == "info":
        if getattr(args, "json", False):
            from .formatters import format_profiles_info_json
            print(format_profiles_info_json(config))
            return 0

        print(f"=== SpecOps Profiles & Invariants ({config.project.name}) ===")
        print("Active Profiles: core, bdd, ddd" + (", security" if config.security else ""))
        print("Preflight Chain: " + " && ".join(config.quality.preflight or ["pytest"]))
        return 0

    else:
        from ..profiles.registry import list_profiles

        profiles = list_profiles()
        print("=== SpecOps Architectural Profiles & Baseline ADRs ===")
        for p in profiles:
            print(f"\n📦 Profile: {p.id} — {p.name}")
            print(f"   {p.description}")
            print("   Baseline ADRs:")
            for adr in p.adrs:
                print(f"     • {adr.canonical_id}: {adr.title}")
        return 0
