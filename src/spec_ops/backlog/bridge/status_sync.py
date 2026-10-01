"""External issue tracker status and commit synchronization bridge (TASK-0107, ADR-0001, ADR-0002)."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any
import urllib.error
import urllib.parse
import urllib.request

from ...config.loader import load_config
from ...config.models import SpecOpsConfig
from ...core.models import Task
from ..queue import BacklogQueue
from .models import ExportSyncResult, ExternalStatusMapping, TaskExportItem


def normalize_spec_ops_status(status: str) -> str:
    """Normalizes task status into canonical SpecOps state."""
    s = (status or "").strip().lower().replace("_", "-").replace(" ", "-")
    if s in ("complete", "completed", "done", "closed", "shipped", "resolved"):
        return "Complete"
    if s in ("in-progress", "inprogress", "active", "claimed", "started", "wip"):
        return "In-Progress"
    if s in ("review", "in-review", "under-review", "reviewing"):
        return "Review"
    if s in ("blocked", "impeded", "stalled"):
        return "Blocked"
    if s in ("refined", "ready", "selected", "todo", "selected-for-development"):
        return "Refined"
    return "Proposed"


def map_status_to_external(status: str, target: str) -> ExternalStatusMapping:
    """Maps SpecOps status to target platform issue status idempotently (ADR-0009)."""
    target_norm = (target or "").strip().lower()
    norm_status = normalize_spec_ops_status(status)

    if target_norm == "jira":
        mapping = {
            "Complete": ("Done", "Done", "Done"),
            "In-Progress": ("In Progress", "In Progress", ""),
            "Review": ("In Review", "In Review", ""),
            "Blocked": ("Blocked", "Blocked", ""),
            "Refined": ("Selected for Development", "Selected for Development", ""),
            "Proposed": ("Backlog", "Backlog", ""),
        }
        state, name, res = mapping.get(norm_status, ("Backlog", "Backlog", ""))
        return ExternalStatusMapping(target="jira", original_status=norm_status, target_state=state, target_status_name=name, resolution=res)

    if target_norm == "linear":
        mapping = {
            "Complete": ("Done", "Done"),
            "In-Progress": ("In Progress", "In Progress"),
            "Review": ("In Review", "In Review"),
            "Blocked": ("Blocked", "Blocked"),
            "Refined": ("Todo", "Todo"),
            "Proposed": ("Backlog", "Backlog"),
        }
        state, name = mapping.get(norm_status, ("Backlog", "Backlog"))
        return ExternalStatusMapping(target="linear", original_status=norm_status, target_state=state, target_status_name=name)

    # Default: GitHub
    if norm_status == "Complete":
        return ExternalStatusMapping(target="github", original_status=norm_status, target_state="closed", target_status_name="closed", labels=["status: completed"], state_reason="completed")
    return ExternalStatusMapping(target="github", original_status=norm_status, target_state="open", target_status_name="open", labels=[f"status: {norm_status.lower()}"])


def parse_github_issue_ref(external_ref: str, default_repo: str = "org/repo") -> tuple[str, str]:
    """Extracts (repo_slug, issue_number) from an external GitHub reference."""
    m = re.search(r"(?:repos/|github\.com/)([^/]+/[^/]+)/issues/(\d+)", external_ref)
    if m:
        return m.group(1), m.group(2)
    m_num = re.search(r"#?(\d+)$", external_ref.strip())
    if m_num:
        repo = os.environ.get("GITHUB_REPO", default_repo)
        return repo, m_num.group(1)
    return default_repo, external_ref.strip().lstrip("#")


def extract_task_external_ticket(task: Task, target: str = "github") -> tuple[str, str]:
    """Resolves external issue key and URL for a task."""
    ref = (task.external_ref or "").strip()
    if ref:
        if ref.startswith("http://") or ref.startswith("https://"):
            m_gh = re.search(r"/issues/(\d+)", ref)
            if m_gh:
                return f"#{m_gh.group(1)}", ref
            m_jira = re.search(r"/(?:browse/)?([A-Z0-9]+-\d+)", ref)
            if m_jira:
                return m_jira.group(1), ref
            m_lin = re.search(r"/issue/([A-Z0-9]+-\d+)", ref)
            if m_lin:
                return m_lin.group(1), ref
            return task.canonical_id, ref
        return ref, ""

    raw = getattr(task, "raw_markdown", "") or getattr(task, "body", "")
    m_raw = re.search(r"(?:external_ref|issue_url|issue):\s*(https?://\S+|[A-Z0-9]+-\d+|#\d+)", raw)
    if m_raw:
        val = m_raw.group(1).strip()
        if val.startswith("http"):
            return extract_task_external_ticket(Task(id=task.id, title=task.title, external_ref=val), target=target)
        return val, ""

    cid = task.canonical_id
    num = re.sub(r"\D", "", cid).lstrip("0") or "1"
    if target == "github":
        return f"#{num}", ""
    if target == "jira":
        return f"CORE-{num}", ""
    if target == "linear":
        return f"ENG-{num}", ""
    return cid, ""


def harvest_task_commits_and_prs(repo_dir: Path, tasks: list[Task]) -> dict[str, dict[str, Any]]:
    """Gathers commit hashes, messages, trailers, and PR references for tasks."""
    from ...core.provenance import extract_commit_records

    records = extract_commit_records(repo_dir)
    by_task: dict[str, dict[str, Any]] = {
        t.canonical_id: {"commits": [], "commit_hashes": [], "pr_references": list(t.prs) if t.prs else ([t.pr_url] if t.pr_url else [])}
        for t in tasks
    }
    for c in records:
        pr_refs: list[str] = [v.strip() for k, v in c.trailers.items() if k.lower() in ("pr", "pull-request", "github-pr", "pullrequest")]
        m_subj_pr = re.search(r"\(#(\d+)\)", c.subject) or re.search(r"Merge pull request #(\d+)", c.subject)
        if m_subj_pr:
            pr_refs.append(f"#{m_subj_pr.group(1)}")

        c_info = {"hash": c.full_hash, "short_hash": c.short_hash, "subject": c.subject, "author": c.author}
        for tid in c.task_ids:
            if tid in by_task:
                if c.full_hash not in by_task[tid]["commit_hashes"]:
                    by_task[tid]["commit_hashes"].append(c.full_hash)
                    by_task[tid]["commits"].append(c_info)
                for pr in pr_refs:
                    if pr not in by_task[tid]["pr_references"]:
                        by_task[tid]["pr_references"].append(pr)
    return by_task


def format_sync_comment(item: TaskExportItem) -> str:
    """Formats markdown comment containing status, commits, and PR references."""
    lines = ["### SpecOps Status Synchronization", f"- **Task**: {item.task_id}: {item.task_title}", f"- **Status**: {item.spec_ops_status}"]
    if item.commits:
        lines.append("- **Commits**:")
        for c in item.commits:
            sh = c.get("short_hash", "") or c.get("hash", "")[:7]
            lines.append(f"  - `{sh}` {c.get('subject', '')} (SpecOps-Task: {item.task_id})")
    elif item.commit_hashes:
        lines.append("- **Commits**:")
        for h in item.commit_hashes:
            lines.append(f"  - `{h[:7]}` (SpecOps-Task: {item.task_id})")
    if item.pr_references:
        lines.append("- **Pull Requests**:")
        for pr in item.pr_references:
            lines.append(f"  - {pr}")
    return "\n".join(lines)


def _http_send(url: str, method: str, data: dict[str, Any], headers: dict[str, str]) -> None:
    req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=15):
        pass


def sync_external_issue(item: TaskExportItem, dry_run: bool = False) -> None:
    """Dispatches issue status updates and comments to external tracker."""
    if dry_run:
        item.synced = False
        item.sync_action = "simulated"
        return

    if item.target == "github":
        _sync_github_issue(item)
    elif item.target == "jira":
        _sync_jira_issue(item)
    elif item.target == "linear":
        _sync_linear_issue(item)
    else:
        item.synced = True
        item.sync_action = "prepared"


def _sync_github_issue(item: TaskExportItem) -> None:
    raw_ref = item.external_url or item.external_key
    repo_slug, issue_num = parse_github_issue_ref(raw_ref)
    base_url = os.environ.get("GITHUB_API_BASE_URL", "https://api.github.com").rstrip("/")
    headers = {"User-Agent": "SpecOps-Bridge", "Accept": "application/vnd.github.v3+json", "Content-Type": "application/json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    patch_body: dict[str, Any] = {}
    if item.status_mapping:
        patch_body["state"] = item.status_mapping.target_state
        if item.status_mapping.state_reason:
            patch_body["state_reason"] = item.status_mapping.state_reason
        if item.status_mapping.labels:
            patch_body["labels"] = item.status_mapping.labels

    try:
        _http_send(f"{base_url}/repos/{repo_slug}/issues/{issue_num}", "PATCH", patch_body, headers)
        _http_send(f"{base_url}/repos/{repo_slug}/issues/{issue_num}/comments", "POST", {"body": item.comment_body}, headers)
        item.synced = True
        item.sync_action = "updated_and_commented"
    except Exception as e:
        item.synced = False
        item.sync_error = str(e)
        item.sync_action = "failed"


def _sync_jira_issue(item: TaskExportItem) -> None:
    base_url = os.environ.get("JIRA_API_BASE_URL", "").rstrip("/")
    if not base_url:
        item.synced = True
        item.sync_action = "prepared"
        return
    headers = {"User-Agent": "SpecOps-Bridge", "Accept": "application/json", "Content-Type": "application/json"}
    token = os.environ.get("JIRA_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        _http_send(f"{base_url}/rest/api/2/issue/{item.external_key}/comment", "POST", {"body": item.comment_body}, headers)
        item.synced = True
        item.sync_action = "updated_and_commented"
    except Exception as e:
        item.synced = False
        item.sync_error = str(e)
        item.sync_action = "failed"


def _sync_linear_issue(item: TaskExportItem) -> None:
    base_url = os.environ.get("LINEAR_API_BASE_URL", "").rstrip("/")
    if not base_url:
        item.synced = True
        item.sync_action = "prepared"
        return
    headers = {"User-Agent": "SpecOps-Bridge", "Content-Type": "application/json"}
    api_key = os.environ.get("LINEAR_API_KEY")
    if api_key:
        headers["Authorization"] = api_key
    try:
        query = {
            "query": "mutation CommentCreate($input: CommentCreateInput!) { commentCreate(input: $input) { success } }",
            "variables": {"input": {"issueId": item.external_key, "body": item.comment_body}},
        }
        _http_send(f"{base_url}/graphql", "POST", query, headers)
        item.synced = True
        item.sync_action = "updated_and_commented"
    except Exception as e:
        item.synced = False
        item.sync_error = str(e)
        item.sync_action = "failed"


def export_tracker_sync(
    backlog_dir: Path,
    target: str = "github",
    sync_status: bool = False,
    dry_run: bool = False,
    config: SpecOpsConfig | None = None,
) -> ExportSyncResult:
    """Exports status synchronization payloads and triggers remote issue updates."""
    cfg = config or load_config(root_dir=backlog_dir.parent.parent)
    repo_dir = getattr(cfg, "root_dir", None) or backlog_dir.parent.parent
    queue = BacklogQueue(backlog_dir)

    all_tasks = queue.list_all_tasks()
    commits_prs_map = harvest_task_commits_and_prs(repo_dir, all_tasks)

    target_norm = (target or "github").lower().strip()
    items: list[TaskExportItem] = []

    for task in all_tasks:
        ext_key, ext_url = extract_task_external_ticket(task, target=target_norm)
        status_map = map_status_to_external(task.status, target=target_norm)
        c_data = commits_prs_map.get(task.canonical_id, {"commits": [], "commit_hashes": [], "pr_references": []})

        item = TaskExportItem(
            task_id=task.canonical_id,
            task_title=task.title,
            spec_ops_status=task.status,
            target=target_norm,
            external_key=ext_key,
            external_url=ext_url,
            status_mapping=status_map,
            commit_hashes=c_data["commit_hashes"],
            commits=c_data["commits"],
            pr_references=c_data["pr_references"],
            sync_action="none",
        )
        item.comment_body = format_sync_comment(item)

        if sync_status:
            sync_external_issue(item, dry_run=dry_run)
        elif dry_run:
            item.sync_action = "simulated"
            item.synced = False
        else:
            item.sync_action = "prepared"
            item.synced = False

        items.append(item)

    synced_count = sum(1 for item in items if item.synced)
    now_iso = datetime.now(timezone.utc).isoformat()

    return ExportSyncResult(
        target=target_norm,
        total_tasks=len(items),
        synced_count=synced_count,
        dry_run=dry_run,
        sync_status=sync_status,
        items=items,
        generated_at=now_iso,
    )
