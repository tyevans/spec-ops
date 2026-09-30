"""Grandfathered file debt baseline tracking for brownfield codebase adoption."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

DEBT_BASELINE_FILE = ".specops/grandfathered_debt.json"

EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "site",
    "storybook-static",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "mutants",
    ".mutmut-cache",
    ".hypothesis",
    ".worktrees",
}

SOURCE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".html",
    ".css",
    ".go",
    ".rs",
    ".java",
    ".cpp",
    ".c",
    ".h",
}


@dataclass
class DebtEvaluation:
    path: str
    current_lines: int
    baseline_lines: int | None
    status: str  # "clean", "grandfathered", "expanded", "unexempt"

    @property
    def is_violation(self) -> bool:
        return self.status in ("expanded", "unexempt")


def normalize_rel_path(path: str | Path) -> str:
    """Normalizes path to forward slashes relative representation."""
    p_str = str(path).replace("\\", "/").strip()
    if p_str.startswith("./"):
        p_str = p_str[2:]
    return p_str


def load_grandfathered_debt(root_dir: Path) -> dict[str, int]:
    """Loads baseline grandfathered debt mapping relative paths to baseline line counts."""
    root = root_dir.resolve()
    debt_map: dict[str, int] = {}

    # 1. Check .specops/grandfathered_debt.json
    json_path = root / DEBT_BASELINE_FILE
    if json_path.is_file():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                files_dict = data.get("files", data) if "files" in data and isinstance(data.get("files"), dict) else data
                for k, v in files_dict.items():
                    if k == "version":
                        continue
                    norm_k = normalize_rel_path(k)
                    if isinstance(v, int):
                        debt_map[norm_k] = v
                    elif isinstance(v, dict) and "line_count" in v and isinstance(v["line_count"], int):
                        debt_map[norm_k] = v["line_count"]
                    elif isinstance(v, dict) and "lines" in v and isinstance(v["lines"], int):
                        debt_map[norm_k] = v["lines"]
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "path" in item and "lines" in item:
                        debt_map[normalize_rel_path(item["path"])] = int(item["lines"])
        except (json.JSONDecodeError, OSError):
            pass

    # 2. Check specops.toml invariants.file_limits.grandfathered
    toml_path = root / "specops.toml"
    if toml_path.is_file():
        try:
            import sys
            if sys.version_info >= (3, 11):
                import tomllib
            else:
                import tomli as tomllib  # type: ignore

            with toml_path.open("rb") as f:
                toml_data = tomllib.load(f)
            toml_files = toml_data.get("invariants", {}).get("file_limits", {}).get("grandfathered", [])
            if not toml_files:
                toml_files = toml_data.get("architecture", {}).get("grandfathered_files", [])
            for item in toml_files:
                norm_p = normalize_rel_path(item)
                if norm_p not in debt_map:
                    # Determine current file line count on disk as baseline if not present
                    target_file = root / norm_p
                    if target_file.is_file():
                        try:
                            lines = len(target_file.read_text(encoding="utf-8", errors="ignore").splitlines())
                            debt_map[norm_p] = lines
                        except OSError:
                            debt_map[norm_p] = 500
                    else:
                        debt_map[norm_p] = 500
        except Exception:
            pass

    return debt_map


def save_grandfathered_debt(root_dir: Path, baseline: dict[str, int]) -> Path:
    """Saves baseline debt into .specops/grandfathered_debt.json."""
    root = root_dir.resolve()
    json_path = root / DEBT_BASELINE_FILE
    json_path.parent.mkdir(parents=True, exist_ok=True)

    normalized_files = {normalize_rel_path(k): int(v) for k, v in sorted(baseline.items())}
    payload = {
        "version": 1,
        "files": normalized_files,
    }
    json_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return json_path


def update_specops_toml_grandfathered(root_dir: Path, grandfathered_files: list[str]) -> Path:
    """Updates or adds [invariants.file_limits] grandfathered list in specops.toml."""
    root = root_dir.resolve()
    toml_path = root / "specops.toml"
    normalized_list = sorted([normalize_rel_path(p) for p in grandfathered_files])

    formatted_entries = "\n".join(f'  "{p}",' for p in normalized_list)
    section_text = f"\n[invariants.file_limits]\ngrandfathered = [\n{formatted_entries}\n]\n"

    if toml_path.is_file():
        content = toml_path.read_text(encoding="utf-8")
        if "[invariants.file_limits]" in content:
            # Replace existing section
            import re
            pattern = r"\[invariants\.file_limits\][\s\S]*?(?=\n\[|\Z)"
            updated = re.sub(pattern, section_text.strip(), content)
            toml_path.write_text(updated.strip() + "\n", encoding="utf-8")
        else:
            toml_path.write_text(content.rstrip() + "\n" + section_text, encoding="utf-8")
    else:
        toml_path.write_text(section_text.strip() + "\n", encoding="utf-8")

    return toml_path


def evaluate_file_debt(
    rel_path: str | Path,
    line_count: int,
    baseline: dict[str, int],
    limit: int = 500,
) -> DebtEvaluation:
    """Evaluates a single file against the grandfathered debt baseline."""
    norm_path = normalize_rel_path(rel_path)
    if norm_path in baseline:
        recorded_baseline = baseline[norm_path]
        if line_count > recorded_baseline:
            return DebtEvaluation(
                path=norm_path,
                current_lines=line_count,
                baseline_lines=recorded_baseline,
                status="expanded",
            )
        return DebtEvaluation(
            path=norm_path,
            current_lines=line_count,
            baseline_lines=recorded_baseline,
            status="grandfathered",
        )

    if line_count > limit:
        return DebtEvaluation(
            path=norm_path,
            current_lines=line_count,
            baseline_lines=None,
            status="unexempt",
        )

    return DebtEvaluation(
        path=norm_path,
        current_lines=line_count,
        baseline_lines=None,
        status="clean",
    )


def scan_and_record_grandfathered_debt(root_dir: Path, limit: int = 500) -> dict[str, int]:
    """Scans all source files in root_dir, baselining oversized files into debt files."""
    root = root_dir.resolve()
    oversized: dict[str, int] = {}

    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel_p = p.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in rel_p.parts):
            continue
        if p.suffix not in SOURCE_EXTENSIONS:
            continue
        try:
            line_count = len(p.read_text(encoding="utf-8", errors="ignore").splitlines())
            if line_count > limit:
                oversized[normalize_rel_path(rel_p)] = line_count
        except (OSError, UnicodeDecodeError):
            continue

    save_grandfathered_debt(root, oversized)
    update_specops_toml_grandfathered(root, list(oversized.keys()))
    return oversized
