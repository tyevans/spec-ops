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

    # 2. Inspect pre-existing documentation tools and workflows
    from ..adopt.detector import deconflict_pages_workflows, inspect_target_doc_systems

    inspection = inspect_target_doc_systems(target_dir)
    for g in inspection.guidance:
        print(f"ℹ️ {g}")

    if getattr(args, "deconflict_workflow", False):
        deconflicted = deconflict_pages_workflows(target_dir)
        for d in deconflicted:
            rel = d.relative_to(target_dir).as_posix()
            print(f"🔧 Deconflicted workflow concurrency in '{rel}'")

    if getattr(args, "bridge_docs", False):
        print("🌉 Documentation Bridging Directives:")
        print("  1. Add navigation link to '/visualizer/' in your legacy doc configuration (e.g. mkdocs.yml)")
        print("  2. Direct build artifacts to co-locate 'site/visualizer/index.html' alongside static pages")
        print("  3. Use '--base-url /<repo>/' to align asset paths across deployment stages")

    # 3. Scaffold self-contained GitHub Pages workflow if requested
    if getattr(args, "github_pages", False):
        from ..scaffold.pages_workflow import generate_pages_workflow

        wf_dir = target_dir / ".github" / "workflows"
        wf_dir.mkdir(parents=True, exist_ok=True)
        wf_file = wf_dir / "deploy-pages.yml"
        wf_content = generate_pages_workflow(project_name=project_name, standalone=True)
        wf_file.write_text(wf_content, encoding="utf-8")
        print("📄 Scaffolded self-contained GitHub Pages workflow at .github/workflows/deploy-pages.yml")

    # 4. Grandfather legacy file debt
    oversized_count = 0
    if grandfather_debt:
        oversized = scan_and_record_grandfathered_debt(
            target_dir,
            limit=config.architecture.file_length_limit,
        )
        oversized_count = len(oversized)

        # 5. Emit refactoring backlog tasks for each grandfathered file
        for rel_path in oversized.keys():
            full_path = target_dir / rel_path
            blueprint = suggest_decomposition(full_path)
            emit_refactor_task(config.backlog_dir, rel_path, blueprint)

    # 6. Install pre-commit security hook and record provenance adoption baseline
    if (target_dir / ".git").exists():
        import subprocess
        from ..security.git_hooks import install_hook

        try:
            install_hook(target_dir)
            print("🔒 Installed pre-commit security hook at .git/hooks/pre-commit")
        except Exception:
            pass

        try:
            head_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=target_dir, capture_output=True, text=True)
            if head_res.returncode == 0 and head_res.stdout.strip():
                head_sha = head_res.stdout.strip()
                toml_file = target_dir / "specops.toml"
                if toml_file.is_file():
                    content = toml_file.read_text(encoding="utf-8")
                    if "[audit.provenance]" not in content:
                        audit_section = f'\n[audit.provenance]\nbaseline_commit = "{head_sha}"\n'
                        toml_file.write_text(content.rstrip() + "\n" + audit_section, encoding="utf-8")
                        print(f"🔒 Configured provenance baseline at commit {head_sha[:8]}")
        except Exception:
            pass

    print(
        f"✨ Adoption complete: {oversized_count} legacy files grandfathered into technical debt baseline"
    )
    print("👉 Run 'spec-ops health' to verify baseline invariants.")
    return 0
