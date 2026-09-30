"""Handler for spec-ops profile CLI commands."""

from __future__ import annotations

import sys
from typing import Any


def handle_profile_command(args: Any, config: Any) -> int:
    """Dispatches profile actions: apply, sync, or list."""
    if args.profile_action == "apply":
        p_name = args.profile_name.lower()
        if p_name == "security":
            from ..profiles.security import apply_security_profile

            apply_security_profile(config.root_dir)
            print(f"✨ Applied '{p_name}' architectural profile to repository.")
            return 0
        else:
            print(f"❌ Unknown profile: {p_name}", file=sys.stderr)
            return 1
    elif args.profile_action == "sync":
        p_name = args.profile_name.lower()
        if p_name == "security":
            from ..profiles.security import sync_security_profile

            sync_security_profile(config.root_dir)
            print(f"✅ Synchronized '{p_name}' architectural profile.")
            return 0
        else:
            print(f"❌ Unknown profile: {p_name}", file=sys.stderr)
            return 1
    elif args.profile_action == "info":
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
