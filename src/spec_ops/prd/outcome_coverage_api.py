"""Public API contracts and HTTP request dispatcher for PRD outcome to BDD test coverage."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .outcome_coverage import PRDOutcomeCoverageEngine, PRDTestCoverageReport


def audit_prd_outcome_coverage_api(
    prd_id_or_path: str | None = None,
    repo_root: Path | str | None = None,
    engine: PRDOutcomeCoverageEngine | None = None,
) -> dict[str, Any]:
    """Public functional API contract auditing PRD checkable outcome and scenario coverage."""
    eng = engine or PRDOutcomeCoverageEngine(repo_root=repo_root)

    if prd_id_or_path:
        rep = eng.audit_prd(prd_id_or_path)
        if rep.prd_title == "Not Found" and rep.total_outcomes == 0:
            return {
                "success": False,
                "error": f"PRD specification not found: {prd_id_or_path}",
                "reports": [],
                "total_prds": 0,
                "fully_covered_prds": 0,
                "total_outcomes": 0,
                "covered_outcomes": 0,
                "overall_outcome_coverage_pct": 0.0,
            }
        return {
            "success": True,
            "reports": [rep.to_dict()],
            "total_prds": 1,
            "fully_covered_prds": 1 if rep.is_fully_covered else 0,
            "total_outcomes": rep.total_outcomes,
            "covered_outcomes": rep.covered_outcomes,
            "overall_outcome_coverage_pct": rep.outcome_coverage_pct,
        }

    reports = eng.audit_all()
    total_prds = len(reports)
    fully_covered = sum(1 for r in reports if r.is_fully_covered)
    total_outcomes = sum(r.total_outcomes for r in reports)
    covered_outcomes = sum(r.covered_outcomes for r in reports)
    pct = (
        round((covered_outcomes / total_outcomes) * 100.0, 1)
        if total_outcomes > 0
        else 100.0
    )

    return {
        "success": True,
        "reports": [r.to_dict() for r in reports],
        "total_prds": total_prds,
        "fully_covered_prds": fully_covered,
        "total_outcomes": total_outcomes,
        "covered_outcomes": covered_outcomes,
        "overall_outcome_coverage_pct": pct,
    }


def dispatch_outcome_coverage_api_request(
    engine: PRDOutcomeCoverageEngine,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    query_params: dict[str, list[str]] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Dispatches HTTP requests to PRD outcome test coverage domain contracts."""
    method_upper = method.strip().upper()
    clean_path = path.split("?")[0].rstrip("/")
    body = payload or {}
    params = query_params or {}

    valid_routes = (
        "/api/prd/coverage/outcomes",
        "/api/prd/outcome-coverage",
        "/api/prd/audit/coverage",
    )

    if clean_path not in valid_routes:
        return 404, {"success": False, "error": f"Endpoint not found: {method_upper} {clean_path}"}

    if method_upper == "GET":
        target = params.get("prd", [None])[0] or params.get("path", [None])[0]
        res = audit_prd_outcome_coverage_api(prd_id_or_path=target, engine=engine)
        return (200 if res.get("success") else 400), res

    if method_upper == "POST":
        target = body.get("prd_id") or body.get("prd") or body.get("path")
        res = audit_prd_outcome_coverage_api(prd_id_or_path=target, engine=engine)
        return (200 if res.get("success") else 400), res

    return 405, {"success": False, "error": f"Method {method_upper} not allowed"}
