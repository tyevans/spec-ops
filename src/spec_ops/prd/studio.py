"""PRD Studio domain service, schema validation, and git commit writeback."""

from __future__ import annotations

import json
import re
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

KNOWN_PERSONAS = {"Alex", "Jordan", "Morgan", "Riley", "Taylor", "Sasha"}


def slugify(text: str) -> str:
    """Converts a title string to a kebab-case URL/filename slug."""
    clean = re.sub(r"[^\w\s-]", "", text.lower())
    clean = re.sub(r"[\s_]+", "-", clean)
    return clean.strip("-")


def serialize_prd_document(frontmatter: dict[str, Any], body: str) -> str:
    """Serializes PRD frontmatter and body into a bit-exact Markdown document."""
    yaml_str = yaml.dump(
        frontmatter,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
    )
    return f"---\n{yaml_str}---\n{body}"


def parse_prd_document(raw_text: str) -> tuple[dict[str, Any], str]:
    """Parses a Markdown document with YAML frontmatter, returning frontmatter and body."""
    if not raw_text.startswith("---\n"):
        return {}, raw_text

    parts = raw_text.split("---\n", 2)
    if len(parts) < 3:
        return {}, raw_text

    raw_yaml = parts[1]
    clean_body = parts[2]

    try:
        data = yaml.safe_load(raw_yaml) or {}
    except Exception:
        data = {}

    return data, clean_body


def validate_prd_schema(data: dict[str, Any]) -> tuple[bool, list[str]]:
    """Validates PRD draft inputs against ADR-0001 quality invariants."""
    violations: list[str] = []

    title = str(data.get("title", "")).strip()
    if not title:
        violations.append("Title is required and cannot be empty.")

    persona = str(data.get("persona") or data.get("target_persona", "")).strip()
    if not persona:
        violations.append("Target persona is required (ADR-0001).")
    elif persona not in KNOWN_PERSONAS:
        violations.append(
            f"Target persona '{persona}' is not recognized. Must be one of: {', '.join(sorted(KNOWN_PERSONAS))}."
        )

    statement = str(data.get("problem_statement", "")).strip()
    if not statement:
        violations.append("Problem statement is required.")

    outcomes = data.get("outcomes", [])
    if isinstance(outcomes, str):
        outcomes = [line.strip("- ").strip() for line in outcomes.splitlines() if line.strip("- ").strip()]
    if not isinstance(outcomes, list) or not any(str(o).strip() for o in outcomes):
        violations.append("At least one checkable outcome is required to satisfy falsifiability (ADR-0001).")

    return (len(violations) == 0, violations)


def find_next_prd_id(product_dir: Path) -> tuple[str, int]:
    """Finds next sequential PRD ID across product folders."""
    max_num = 0
    if product_dir.exists():
        for p in product_dir.rglob("*.md"):
            m = re.search(r"prd-(\d+)", p.stem, re.IGNORECASE)
            if m:
                val = int(m.group(1))
                if val > max_num:
                    max_num = val
    next_num = max_num + 1
    return f"PRD-{next_num:04d}", next_num


def create_prd_draft(
    repo_root: Path,
    data: dict[str, Any],
) -> dict[str, Any]:
    """Scaffolds a new PRD draft file in docs/project/product/idea/."""
    valid, violations = validate_prd_schema(data)
    if not valid:
        return {
            "success": False,
            "error": "Validation Error (ADR-0001)",
            "violations": violations,
            "message": "PRD schema validation failed: " + "; ".join(violations),
        }

    root = Path(repo_root).resolve()
    product_dir = root / "docs" / "project" / "product"
    idea_dir = product_dir / "idea"
    idea_dir.mkdir(parents=True, exist_ok=True)

    title = str(data["title"]).strip()
    persona = str(data.get("persona") or data.get("target_persona", "")).strip()
    component = str(data.get("component", "core")).strip() or "core"
    problem_statement = str(data["problem_statement"]).strip()
    outcomes = data.get("outcomes", [])
    if isinstance(outcomes, str):
        outcomes = [line.strip("- ").strip() for line in outcomes.splitlines() if line.strip("- ").strip()]
    clean_outcomes = [str(o).strip() for o in outcomes if str(o).strip()]

    explicit_id = data.get("prd_id")
    if explicit_id:
        digits = re.findall(r"\d+", str(explicit_id))
        num = int(digits[-1]) if digits else 1
        prd_id = f"PRD-{num:04d}"
        num_str = f"{num:04d}"
    else:
        prd_id, num = find_next_prd_id(product_dir)
        num_str = f"{num:04d}"

    slug = slugify(title)
    filename = f"prd-{num_str}-{slug}.md"
    target_path = idea_dir / filename

    frontmatter = {
        "id": prd_id,
        "title": title,
        "status": "Idea",
        "target_persona": persona,
        "component": component,
    }

    outcomes_formatted = "\n".join(f"- {o}" for o in clean_outcomes)
    body = (
        f"# {prd_id}: {title}\n\n"
        "## Problem Statement\n"
        f"{problem_statement}\n\n"
        "## Checkable Outcomes\n"
        f"{outcomes_formatted}\n"
    )

    full_content = serialize_prd_document(frontmatter, body)
    target_path.write_text(full_content, encoding="utf-8")

    rel_path = str(target_path.relative_to(root))
    return {
        "success": True,
        "prd_id": prd_id,
        "title": title,
        "file_path": rel_path,
        "absolute_path": str(target_path),
        "content": full_content,
        "message": f"Created PRD draft {prd_id} at {rel_path}",
    }


def commit_prd_specification(
    repo_root: Path,
    file_path: str | Path,
    content: str,
    commit_message: str | None = None,
    author_name: str = "Taylor",
    author_email: str = "taylor@specops.local",
) -> dict[str, Any]:
    """Writes updated PRD content and commits directly to active git feature branch."""
    root = Path(repo_root).resolve()
    target_file = (root / file_path).resolve()

    start_time = time.perf_counter()

    # 1. Write content to file
    target_file.parent.mkdir(parents=True, exist_ok=True)
    target_file.write_text(content, encoding="utf-8")

    # 2. Stage with git add
    rel_path = str(target_file.relative_to(root))
    add_res = subprocess.run(["git", "add", rel_path], cwd=root, capture_output=True, text=True)
    if add_res.returncode != 0:
        return {
            "success": False,
            "error": "Git add failed",
            "message": add_res.stderr.strip(),
        }

    # 3. Commit with author attribution
    msg = commit_message or f"spec(prd): update specification {target_file.name}"
    author_flag = f"{author_name} <{author_email}>"
    commit_res = subprocess.run(
        ["git", "commit", "-m", msg, f"--author={author_flag}"],
        cwd=root,
        capture_output=True,
        text=True,
    )

    # 4. Get commit hash if successful
    commit_hash = ""
    if commit_res.returncode == 0:
        rev_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
        commit_hash = rev_res.stdout.strip()
    else:
        # Check if working tree was clean (no changes to commit)
        if "nothing to commit" in commit_res.stdout or "nothing to commit" in commit_res.stderr:
            rev_res = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True, text=True)
            commit_hash = rev_res.stdout.strip()
        else:
            return {
                "success": False,
                "error": "Git commit failed",
                "message": commit_res.stderr.strip() or commit_res.stdout.strip(),
            }

    elapsed_ms = (time.perf_counter() - start_time) * 1000

    return {
        "success": True,
        "commit_hash": commit_hash,
        "file_path": rel_path,
        "latency_ms": round(elapsed_ms, 2),
        "message": f"Committed specification {rel_path} in {elapsed_ms:.1f}ms ({commit_hash[:7]})",
    }
