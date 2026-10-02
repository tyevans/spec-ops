"""Public HTTP/JSON API dispatch contracts for PRD Studio web interface."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

from .studio_state import PRDStudioStateManager


def dispatch_studio_api_request(
    manager: PRDStudioStateManager,
    method: str,
    path: str,
    payload: dict[str, Any] | None = None,
    query_params: dict[str, list[str]] | None = None,
) -> tuple[int, dict[str, Any]]:
    """Dispatches HTTP requests to PRDStudioStateManager domain methods."""
    method_upper = method.strip().upper()
    clean_path = path.split("?")[0].rstrip("/")
    body = payload or {}
    params = query_params or {}

    if method_upper == "GET":
        if clean_path in ("/api/studio/state", "/api/studio/session"):
            return 200, {"success": True, "state": manager.to_dict()}

        if clean_path == "/api/studio/prds":
            prds = [asdict(p) for p in manager.list_prds()]
            return 200, {"success": True, "prds": prds, "total": len(prds)}

        if clean_path == "/api/studio/draft/load":
            prd_id = params.get("prd_id", [None])[0] or params.get("id", [None])[0]
            if not prd_id:
                return 400, {"success": False, "error": "Missing 'prd_id' query parameter"}
            ok = manager.load_prd(prd_id)
            if ok:
                return 200, {"success": True, "state": manager.to_dict()}
            return 404, {"success": False, "error": f"PRD '{prd_id}' not found"}

        return 404, {"success": False, "error": f"Studio endpoint not found: GET {clean_path}"}

    if method_upper == "POST":
        if clean_path == "/api/studio/draft/new":
            manager.new_draft(
                title=str(body.get("title", "")),
                persona=str(body.get("persona", "")),
                component=str(body.get("component", "core")),
                problem_statement=str(body.get("problem_statement", "")),
                outcomes=body.get("outcomes"),
            )
            return 200, {"success": True, "state": manager.to_dict()}

        if clean_path == "/api/studio/draft/update":
            field_name = str(body.get("field", ""))
            if not field_name:
                return 400, {"success": False, "error": "Missing 'field' in update payload"}
            val = body.get("value")
            try:
                is_valid, errors = manager.update_field(field_name, val)
                return 200, {
                    "success": True,
                    "is_valid": is_valid,
                    "validation_errors": errors,
                    "state": manager.to_dict(),
                }
            except KeyError as err:
                return 400, {"success": False, "error": str(err)}

        if clean_path == "/api/studio/draft/outcome/add":
            outcome_text = str(body.get("outcome") or body.get("text", "")).strip()
            if not outcome_text:
                return 400, {"success": False, "error": "Missing 'outcome' text in payload"}
            is_valid, errors = manager.add_outcome(outcome_text)
            return 200, {
                "success": True,
                "is_valid": is_valid,
                "validation_errors": errors,
                "state": manager.to_dict(),
            }

        if clean_path == "/api/studio/draft/outcome/remove":
            idx = body.get("index")
            if idx is None or not isinstance(idx, int):
                return 400, {"success": False, "error": "Missing integer 'index' parameter"}
            ok = manager.remove_outcome(idx)
            if ok:
                return 200, {"success": True, "state": manager.to_dict()}
            return 400, {"success": False, "error": f"Invalid outcome index: {idx}"}

        if clean_path == "/api/studio/draft/outcome/reorder":
            order = body.get("order")
            if not isinstance(order, list) or not all(isinstance(x, int) for x in order):
                return 400, {"success": False, "error": "Payload must provide 'order' list of integers"}
            ok = manager.reorder_outcomes(order)
            if ok:
                return 200, {"success": True, "state": manager.to_dict()}
            return 400, {"success": False, "error": "Invalid permutation sequence"}

        if clean_path == "/api/studio/draft/load":
            prd_id = body.get("prd_id") or body.get("id")
            if not prd_id:
                return 400, {"success": False, "error": "Missing 'prd_id' in payload"}
            ok = manager.load_prd(str(prd_id))
            if ok:
                return 200, {"success": True, "state": manager.to_dict()}
            return 404, {"success": False, "error": f"PRD '{prd_id}' not found"}

        if clean_path == "/api/studio/draft/save":
            res = manager.save_draft()
            code = 200 if res.get("success") else 400
            res["state"] = manager.to_dict()
            return code, res

        if clean_path == "/api/studio/draft/commit":
            res = manager.commit_changes(
                commit_message=body.get("commit_message"),
                author_name=body.get("author_name", "Taylor"),
                author_email=body.get("author_email", "taylor@specops.local"),
            )
            code = 200 if res.get("success") else 400
            res["state"] = manager.to_dict()
            return code, res

        if clean_path == "/api/studio/draft/promote":
            target_stage = body.get("stage") or body.get("target_stage")
            if not target_stage:
                return 400, {"success": False, "error": "Missing 'stage' parameter"}
            res = manager.promote_stage(str(target_stage))
            code = 200 if res.get("success") else 400
            res["state"] = manager.to_dict()
            return code, res

        return 404, {"success": False, "error": f"Studio endpoint not found: POST {clean_path}"}

    return 405, {"success": False, "error": f"Method {method_upper} not allowed"}
