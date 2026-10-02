"""Public API contracts and HTTP dispatcher for PRD line-level linting and remediation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .lint_engine import PRDLintEngine, PRDLintReport


def lint_prd_api(
    prd_id_or_path: str | None = None,
    repo_root: Path | str | None = None,
    engine: PRDLintEngine | None = None,
) -> dict[str, Any]:
    """Public functional API contract executing PRD line-level quality audit."""
    root = Path(repo_root or Path.cwd()).resolve()
    eng = engine or PRDLintEngine(root_dir=root)
    prd_dir = root / "docs" / "project" / "product"

    if prd_id_or_path:
        candidate = Path(prd_id_or_path)
        target: Path | None = candidate if candidate.is_file() else None
        if not target and prd_dir.exists():
            clean_id = prd_id_or_path.strip().lower()
            for f in prd_dir.rglob("*.md"):
                if f.name == "REGISTRY.md":
                    continue
                if clean_id in f.stem.lower():
                    target = f
                    break
        if not target or not target.exists():
            return {
                "success": False,
                "error": f"PRD specification not found: {prd_id_or_path}",
                "reports": [],
                "total_files": 0,
                "valid_files": 0,
                "total_errors": 1,
            }
        report = eng.lint_file(target)
        return {
            "success": True,
            "reports": [report.to_dict()],
            "total_files": 1,
            "valid_files": 1 if report.is_valid else 0,
            "total_errors": report.error_count,
            "total_warnings": report.warning_count,
        }

    reports: list[dict[str, Any]] = []
    total_files = 0
    valid_files = 0
    total_errors = 0
    total_warnings = 0

    if prd_dir.exists():
        for stage in ("idea", "shaped", "accepted", "shipped"):
            s_dir = prd_dir / stage
            if not s_dir.exists():
                continue
            for f in sorted(s_dir.glob("*.md")):
                if f.name == "REGISTRY.md":
                    continue
                rep = eng.lint_file(f)
                reports.append(rep.to_dict())
                total_files += 1
                if rep.is_valid:
                    valid_files += 1
                total_errors += rep.error_count
                total_warnings += rep.warning_count

    return {
        "success": True,
        "reports": reports,
        "total_files": total_files,
        "valid_files": valid_files,
        "total_errors": total_errors,
        "total_warnings": total_warnings,
    }


def dispatch_lint_api_request(
    engine: PRDLintEngine,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    query_params: dict[str, list[str]] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Dispatches HTTP requests to PRD lint engine domain contracts."""
    method_upper = method.strip().upper()
    clean_path = path.split("?")[0].rstrip("/")
    body = payload or {}
    params = query_params or {}

    if method_upper == "GET":
        if clean_path in ("/api/prd/lint", "/api/prd/lint/status"):
            target_path = params.get("path", [None])[0] or params.get("prd", [None])[0]
            res = lint_prd_api(
                prd_id_or_path=target_path,
                repo_root=engine.root_dir,
                engine=engine,
            )
            return (200 if res.get("success") else 400), res

        return 404, {"success": False, "error": f"Endpoint not found: GET {clean_path}"}

    if method_upper == "POST":
        if clean_path == "/api/prd/lint":
            content = body.get("content")
            if content is not None:
                rep = engine.lint_content(content, file_path=body.get("file_path", "<in-memory>"))
                return 200, {"success": True, "report": rep.to_dict()}

            target_path = body.get("path") or body.get("prd_id")
            res = lint_prd_api(
                prd_id_or_path=target_path,
                repo_root=engine.root_dir,
                engine=engine,
            )
            return (200 if res.get("success") else 400), res

        if clean_path == "/api/prd/lint/remediate":
            content = body.get("content", "")
            if not content:
                return 400, {"success": False, "error": "Missing 'content' to remediate"}
            rep = engine.lint_content(content)
            remediated_lines = content.splitlines()

            applied_count = 0
            for d in rep.diagnostics:
                if d.suggestion and 1 <= d.suggestion.line <= len(remediated_lines):
                    remediated_lines[d.suggestion.line - 1] = d.suggestion.suggested_text
                    applied_count += 1

            new_content = "\n".join(remediated_lines) + "\n"
            new_rep = engine.lint_content(new_content)
            return 200, {
                "success": True,
                "applied_count": applied_count,
                "remediated_content": new_content,
                "new_report": new_rep.to_dict(),
            }

        return 404, {"success": False, "error": f"Endpoint not found: POST {clean_path}"}

    return 405, {"success": False, "error": f"Method {method_upper} not allowed"}
