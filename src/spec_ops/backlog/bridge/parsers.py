"""Parsers for GitHub, Jira, and Linear issue formats (ADR-0001, ADR-0002)."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .models import ExternalIssue


def extract_bc_from_labels_or_text(labels: list[str], text: str) -> str:
    """Extracts bounded context token from issue labels or description text."""
    for lbl in labels:
        if lbl.startswith("bc:") or lbl.startswith("component:"):
            return lbl.split(":", 1)[1].strip()
    m = re.search(r"(?:target_bc|bounded\s+context|bc):\s*([a-zA-Z0-9_\-]+)", text, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return "core"


def extract_dependencies_from_text(text: str) -> list[str]:
    """Extracts dependency tokens from markdown or plain text."""
    deps: list[str] = []
    m = re.search(r"(?:depends\s+on|blocked\s+by|dependencies):\s*([^\n]+)", text, re.IGNORECASE)
    if m:
        for part in m.group(1).split(","):
            token = part.strip().strip("[]'\"")
            if token:
                deps.append(token)
    return deps


def parse_github_items(data: Any) -> list[ExternalIssue]:
    """Normalizes GitHub issues payload into ExternalIssue objects."""
    raw_list = data if isinstance(data, list) else data.get("items", data.get("issues", []))
    issues: list[ExternalIssue] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        num = str(item.get("number") or item.get("id") or "")
        title = str(item.get("title") or "")
        body = str(item.get("body") or "")
        url = str(item.get("html_url") or item.get("url") or "")
        labels = [str(l.get("name") if isinstance(l, dict) else l) for l in item.get("labels", [])]
        bc = extract_bc_from_labels_or_text(labels, body)
        deps = extract_dependencies_from_text(body)
        issues.append(
            ExternalIssue(
                key=f"#{num}" if num.isdigit() else num,
                title=title,
                description=body,
                status=str(item.get("state", "open")),
                url=url,
                target_bc=bc,
                dependencies=deps,
                labels=labels,
                source="github",
                raw_payload=item,
            )
        )
    return issues


def parse_jira_items(data: Any) -> list[ExternalIssue]:
    """Normalizes Jira JSON export issues into ExternalIssue objects."""
    raw_list = data.get("issues", data) if isinstance(data, dict) else data
    if not isinstance(raw_list, list):
        raw_list = [data] if isinstance(data, dict) else []

    issues: list[ExternalIssue] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "")
        fields = item.get("fields", item)
        title = str(fields.get("summary") or item.get("summary") or "")
        desc = fields.get("description", "")
        desc_text = desc if isinstance(desc, str) else json.dumps(desc)
        status_val = fields.get("status", "Open")
        status = status_val.get("name", "Open") if isinstance(status_val, dict) else str(status_val)
        url = str(item.get("self") or fields.get("url") or item.get("url") or "")

        labels = [str(l) for l in fields.get("labels", [])]
        components = fields.get("components", [])
        if components and isinstance(components, list):
            first_comp = components[0]
            bc = first_comp.get("name", "core") if isinstance(first_comp, dict) else str(first_comp)
        else:
            bc = extract_bc_from_labels_or_text(labels, desc_text)

        deps: list[str] = []
        for link in fields.get("issuelinks", []):
            if not isinstance(link, dict):
                continue
            type_info = link.get("type", {})
            type_name = str(type_info.get("name", "")).lower()
            inward = str(type_info.get("inward", "")).lower()
            if "block" in type_name or "block" in inward or "depend" in inward:
                if "inwardIssue" in link:
                    deps.append(str(link["inwardIssue"].get("key", "")))
                elif "outwardIssue" in link and "blocks" in inward:
                    deps.append(str(link["outwardIssue"].get("key", "")))
        if "dependencies" in fields and isinstance(fields["dependencies"], list):
            deps.extend([str(d) for d in fields["dependencies"]])
        deps.extend(extract_dependencies_from_text(desc_text))

        issues.append(
            ExternalIssue(
                key=key,
                title=title,
                description=desc_text,
                status=status,
                url=url,
                target_bc=bc,
                dependencies=sorted(set(filter(None, deps))),
                labels=labels,
                source="jira",
                raw_payload=item,
            )
        )
    return issues


def parse_linear_items(data: Any) -> list[ExternalIssue]:
    """Normalizes Linear JSON export issues into ExternalIssue objects."""
    raw_list = data
    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], dict) and "issues" in data["data"]:
            raw_list = data["data"]["issues"]
        elif "issues" in data:
            raw_list = data["issues"]
        else:
            raw_list = [data]

    issues: list[ExternalIssue] = []
    for item in raw_list:
        if not isinstance(item, dict):
            continue
        key = str(item.get("identifier") or item.get("key") or item.get("id") or "")
        title = str(item.get("title") or "")
        desc = str(item.get("description") or "")
        url = str(item.get("url") or "")
        state = item.get("state", {})
        status = state.get("name", "Todo") if isinstance(state, dict) else str(state)

        deps: list[str] = []
        if "parent" in item and isinstance(item["parent"], dict):
            p_id = item["parent"].get("identifier") or item["parent"].get("key")
            if p_id:
                deps.append(str(p_id))
        for rel in item.get("relations", []):
            if isinstance(rel, dict) and str(rel.get("type", "")).lower() in ("blocked_by", "depends_on"):
                rel_issue = rel.get("relatedIssue", {})
                rel_id = rel_issue.get("identifier") or rel_issue.get("key")
                if rel_id:
                    deps.append(str(rel_id))
        if "dependencies" in item and isinstance(item["dependencies"], list):
            deps.extend([str(d) for d in item["dependencies"]])
        deps.extend(extract_dependencies_from_text(desc))

        bc = extract_bc_from_labels_or_text([], desc)
        issues.append(
            ExternalIssue(
                key=key,
                title=title,
                description=desc,
                status=status,
                url=url,
                target_bc=bc,
                dependencies=sorted(set(filter(None, deps))),
                source="linear",
                raw_payload=item,
            )
        )
    return issues


def parse_csv_content(content: str, source: str = "auto") -> list[ExternalIssue]:
    """Parses exported CSV content into normalized ExternalIssue objects."""
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return []

    headers = {h.strip().lower() for h in (reader.fieldnames or [])}
    detected = source
    if detected == "auto":
        if "issue key" in headers or "summary" in headers:
            detected = "jira"
        elif "identifier" in headers:
            detected = "linear"
        else:
            detected = "github"

    issues: list[ExternalIssue] = []
    for row in rows:
        clean = {k.strip().lower(): v for k, v in row.items() if k}
        key = (
            clean.get("issue key")
            or clean.get("key")
            or clean.get("identifier")
            or clean.get("id")
            or clean.get("issue number")
            or ""
        )
        title = clean.get("summary") or clean.get("title") or ""
        desc = clean.get("description") or clean.get("body") or ""
        url = clean.get("url") or clean.get("link") or ""
        status = clean.get("status") or clean.get("state") or "open"

        deps: list[str] = []
        for col, val in clean.items():
            if any(w in col for w in ("blocked by", "depends on", "dependencies", "parent")):
                for token in str(val).split(","):
                    if token.strip():
                        deps.append(token.strip())
        deps.extend(extract_dependencies_from_text(desc))

        bc = clean.get("component") or clean.get("component/s") or clean.get("target_bc") or ""
        if not bc:
            bc = extract_bc_from_labels_or_text([], desc)

        issues.append(
            ExternalIssue(
                key=key,
                title=title,
                description=desc,
                status=status,
                url=url,
                target_bc=bc or "core",
                dependencies=sorted(set(filter(None, deps))),
                source=detected,
                raw_payload=row,
            )
        )
    return issues


def detect_json_source(data: Any) -> str:
    """Detects issue tracker source from loaded JSON structure."""
    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], dict) and "issues" in data["data"]:
            return "linear"
        if "issues" in data and isinstance(data["issues"], list):
            if data["issues"] and "fields" in data["issues"][0]:
                return "jira"
            if data["issues"] and "identifier" in data["issues"][0]:
                return "linear"
        if "key" in data and "fields" in data:
            return "jira"
    elif isinstance(data, list) and data:
        first = data[0]
        if isinstance(first, dict):
            if "identifier" in first:
                return "linear"
            if "key" in first and ("fields" in first or "summary" in first):
                return "jira"
            if "html_url" in first or "number" in first:
                return "github"
    return "github"


def fetch_github_remote(repo: str, label: str | None = None) -> list[ExternalIssue]:
    """Fetches issues from GitHub REST API."""
    base_url = os.environ.get("GITHUB_API_BASE_URL", "https://api.github.com").rstrip("/")
    api_url = f"{base_url}/repos/{repo}/issues?state=open"
    if label:
        api_url += f"&labels={urllib.parse.quote(label)}"

    headers = {"User-Agent": "SpecOps-Bridge", "Accept": "application/vnd.github.v3+json"}
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"

    req = urllib.request.Request(api_url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"GitHub API HTTP error ({e.code}): {e.reason} for repository {repo}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Failed to connect to GitHub API: {e.reason}") from e
    except TimeoutError as e:
        raise RuntimeError(f"Timed out fetching issues from GitHub repository {repo}") from e

    if not isinstance(data, list):
        return []

    issues_data = [item for item in data if "pull_request" not in item]
    return parse_github_items(issues_data)
