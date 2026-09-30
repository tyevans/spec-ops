"""CLI command handler for brownfield codebase adoption and debt baselining."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from ..config.loader import load_config
from ..core.ast_seams import emit_refactor_task, suggest_decomposition
from ..core.debt_baseline import scan_and_record_grandfathered_debt
from ..scaffold.init import init_project


def handle_adopt_command(args: Any) -> int:
    """Executes 'spec-ops adopt' for brownfield repository onboarding."""
    target_dir = Path(getattr(args, "dir", ".")).resolve()
    profile_str = getattr(args, "profile", "core,bdd,ddd") or "core,bdd,ddd"
    profile_list = [p.strip() for p in profile_str.split(",") if p.strip()]
    project_name = getattr(args, "name", None) or target_dir.name
    grandfather_debt = getattr(args, "grandfather_debt", True)

    # 1. Initialize SpecOps structure if not already present
    try:
        init_project(
            target_dir,
            name=project_name,
            profiles=profile_list,
        )
    except Exception as err:
        print(f"❌ Adoption initialization error: {err}", file=sys.stderr)
        return 1

    config = load_config(root_dir=target_dir)

    # 2. Grandfather legacy file debt
    oversized_count = 0
    if grandfather_debt:
        oversized = scan_and_record_grandfathered_debt(
            target_dir,
            limit=config.architecture.file_length_limit,
        )
        oversized_count = len(oversized)

        # 3. Emit refactoring backlog tasks for each grandfathered file
        for rel_path in oversized.keys():
            full_path = target_dir / rel_path
            blueprint = suggest_decomposition(full_path)
            emit_refactor_task(config.backlog_dir, rel_path, blueprint)

    print(
        f"✨ Adoption complete: {oversized_count} legacy files grandfathered into technical debt baseline"
    )
    print("👉 Run 'spec-ops health' to verify baseline invariants.")
    return 0
