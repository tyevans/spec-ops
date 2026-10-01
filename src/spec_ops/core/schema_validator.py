"""Specification frontmatter schema validation against active Pydantic models."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .ast_parser import FrontmatterDiagnosticError, parse_markdown_document

SCHEMA_VERSION = "v2.0"

LEGACY_FIELD_HINTS: dict[str, str] = {
    "governing_adr": "governing_adrs (e.g. ['ADR-0001'])",
    "governing_prd": "governing_prds (e.g. ['PRD-0005'])",
    "governing_story": "governing_stories (e.g. ['US-0017'])",
    "story": "governing_stories (e.g. ['US-0017'])",
    "stories": "governing_stories (e.g. ['US-0017'])",
    "prd": "governing_prds (e.g. ['PRD-0005'])",
    "dependency": "dependencies (e.g. ['TASK-0001'])",
}


class TaskFrontmatter(BaseModel):
    """Pydantic schema model for Task specification frontmatter."""

    model_config = ConfigDict(extra="forbid")

    id: Any
    title: str
    status: str
    target_bc: str = "core"
    dependencies: list[Any] = Field(default_factory=list)
    governing_adrs: list[Any] = Field(default_factory=list)
    governing_prds: list[Any] = Field(default_factory=list)
    governing_stories: list[Any] = Field(default_factory=list)
    created: Any = None
    completed: Any = None
    claimed_by: Optional[str] = None
    branch: Optional[str] = None
    prs: list[str] = Field(default_factory=list)
    pr_url: Optional[str] = None
    priority_rank: Optional[int] = None
    allows_dependencies: bool = False
    hypothesis: Optional[str] = None
    timebox: Optional[str] = None
    signed_off_by: Optional[str] = None
    signed_off_at: Optional[str] = None
    has_signed_commits: Optional[bool] = None
    commit_signature_status: Optional[str] = None
    blocker: Any = None
    slice_type: Optional[str] = None
    failure_history: list[Any] = Field(default_factory=list)
    external_ref: Optional[str] = None
    issue_url: Optional[str] = None


class UserStoryFrontmatter(BaseModel):
    """Pydantic schema model for User Story specification frontmatter."""

    model_config = ConfigDict(extra="forbid")

    id: Any
    title: str
    status: str = "Accepted"
    created: Any = None
    persona: str
    feature: str
    governing_prd: str


class PRDFrontmatter(BaseModel):
    """Pydantic schema model for PRD specification frontmatter."""

    model_config = ConfigDict(extra="forbid")

    id: Any
    title: str
    status: str = "Accepted"
    created: Any = None
    target_persona: str
    component: str


class ADRFrontmatter(BaseModel):
    """Pydantic schema model for ADR frontmatter when present."""

    model_config = ConfigDict(extra="allow")

    id: Any
    title: str
    status: str = "Accepted"
    domain: Optional[str] = "Architecture"


@dataclass
class SchemaDiagnosticError:
    """Diagnostic error pointing to exact file, line, and column."""

    file_path: str
    line: int
    column: int
    message: str
    source_snippet: str = ""
    hint: str = ""

    def format_error(self) -> str:
        snippet_part = ""
        if self.source_snippet:
            snippet_part = (
                f"|\n"
                f"{self.line} | {self.source_snippet}\n"
                f"| {' ' * max(0, self.column - 1)}^ {self.message}"
            )
        else:
            snippet_part = f"| {self.message}"

        hint_part = f"\nhint: {self.hint}" if self.hint else ""
        return (
            f"error: Schema Validation Error in {self.file_path}:{self.line}:{self.column}\n"
            f"{snippet_part}{hint_part}"
        )

    def __str__(self) -> str:
        return self.format_error()


def detect_document_type(file_path: Path | str, meta: dict[str, Any] | None = None) -> str:
    """Determines specification document type from path and frontmatter clues."""
    path_obj = Path(file_path)
    parts = [p.lower() for p in path_obj.parts]

    if "user_stories" in parts or path_obj.name.lower().startswith("us-"):
        return "story"
    if "product" in parts or path_obj.name.lower().startswith("prd-"):
        return "prd"
    if "backlog" in parts or path_obj.name.lower().startswith("task-"):
        return "task"
    if "adrs" in parts or path_obj.name.lower().startswith("adr-"):
        return "adr"

    if meta:
        if "target_persona" in meta or "component" in meta:
            return "prd"
        if "persona" in meta or "feature" in meta or "governing_prd" in meta:
            return "story"
        if "target_bc" in meta or "dependencies" in meta or "governing_adrs" in meta or "governing_adr" in meta:
            return "task"

    return "task"


def get_field_locations(yaml_text: str, offset: int = 2) -> dict[str, tuple[int, int]]:
    """Extracts line and column numbers for all top-level keys in YAML frontmatter."""
    clean = yaml_text[1:] if yaml_text.startswith("\n") else yaml_text
    try:
        node = yaml.compose(clean)
    except Exception:
        return {}

    if not isinstance(node, yaml.MappingNode):
        return {}

    locations: dict[str, tuple[int, int]] = {}
    for key_node, _ in node.value:
        if isinstance(key_node, yaml.ScalarNode):
            line = key_node.start_mark.line + offset
            col = key_node.start_mark.column + 1
            locations[str(key_node.value)] = (line, col)
    return locations


def validate_frontmatter_dict(
    meta: dict[str, Any],
    doc_type: str,
    file_path: str = "",
    yaml_text: str = "",
    file_lines: list[str] | None = None,
) -> list[SchemaDiagnosticError]:
    """Validates frontmatter dictionary against appropriate Pydantic model."""
    lines = file_lines or []
    locations = get_field_locations(yaml_text) if yaml_text else {}

    # Check for legacy fields first to provide precise hints
    errors: list[SchemaDiagnosticError] = []
    if doc_type == "task":
        for legacy_k, replacement in LEGACY_FIELD_HINTS.items():
            if legacy_k in meta:
                loc = locations.get(legacy_k, (2, 1))
                snippet = lines[loc[0] - 1] if 0 < loc[0] <= len(lines) else f"{legacy_k}: {meta[legacy_k]}"
                errors.append(
                    SchemaDiagnosticError(
                        file_path=file_path,
                        line=loc[0],
                        column=loc[1],
                        message=f"Legacy field '{legacy_k}' is deprecated in schema {SCHEMA_VERSION}",
                        source_snippet=snippet,
                        hint=f"Use '{replacement}' instead. Run 'spec-ops schema migrate --in-place' to upgrade.",
                    )
                )

    model_map: dict[str, type[BaseModel]] = {
        "task": TaskFrontmatter,
        "story": UserStoryFrontmatter,
        "prd": PRDFrontmatter,
        "adr": ADRFrontmatter,
    }
    model_cls = model_map.get(doc_type, TaskFrontmatter)

    try:
        model_cls.model_validate(meta)
    except ValidationError as val_err:
        for err in val_err.errors():
            loc_tuple = err.get("loc", ())
            field_name = str(loc_tuple[0]) if loc_tuple else "frontmatter"
            err_type = err.get("type", "")
            err_msg = err.get("msg", "Invalid value")

            # Avoid duplicating legacy field errors already recorded
            if field_name in LEGACY_FIELD_HINTS and any(e.message.find(f"'{field_name}'") != -1 for e in errors):
                continue

            if field_name in locations:
                line_num, col_num = locations[field_name]
            else:
                line_num, col_num = (2, 1)

            snippet = lines[line_num - 1] if 0 < line_num <= len(lines) else ""
            if err_type == "missing":
                msg = f"Missing required field '{field_name}' for schema {SCHEMA_VERSION}"
            elif err_type == "extra_forbidden":
                msg = f"Forbidden extra field '{field_name}' in schema {SCHEMA_VERSION}"
            else:
                msg = f"Field '{field_name}': {err_msg}"

            errors.append(
                SchemaDiagnosticError(
                    file_path=file_path,
                    line=line_num,
                    column=col_num,
                    message=msg,
                    source_snippet=snippet,
                )
            )

    return errors


def validate_document(content: str, file_path: Path | str = "") -> list[SchemaDiagnosticError]:
    """Validates markdown document frontmatter syntax and schema conformance."""
    str_path = str(file_path)
    file_lines = content.splitlines()

    try:
        meta, _ = parse_markdown_document(content, file_path=str_path)
    except FrontmatterDiagnosticError as fm_err:
        return [
            SchemaDiagnosticError(
                file_path=str_path,
                line=fm_err.line,
                column=fm_err.column,
                message=fm_err.message,
                source_snippet=fm_err.source_snippet,
                hint=fm_err.hint,
            )
        ]

    # Extract raw YAML text for location tracking
    yaml_text = ""
    if content.startswith("---"):
        rest = content[3:]
        m = re.search(r"(\r?\n)---[ \t]*(\r?\n|\Z)", rest)
        if m:
            yaml_text = rest[: m.start()]

    doc_type = detect_document_type(str_path, meta)
    return validate_frontmatter_dict(meta, doc_type, str_path, yaml_text, file_lines)


def is_specification_file(path: Path) -> bool:
    """Identifies whether a file is a PMaC specification document subject to schema audit."""
    if path.suffix.lower() != ".md":
        return False

    ignored_names = {
        "priority.md",
        "roadmap.md",
        "registry.md",
        "personas.md",
        "readme.md",
        "security.md",
    }
    if path.name.lower() in ignored_names:
        return False

    parts = [p.lower() for p in path.parts]
    if "docs" in parts and "project" in parts:
        if "adrs" in parts:
            try:
                txt = path.read_text(encoding="utf-8")
                return txt.startswith("---")
            except OSError:
                return False
        return True

    try:
        txt = path.read_text(encoding="utf-8")
        return txt.startswith("---")
    except OSError:
        return False


def collect_specification_files(target: Path) -> list[Path]:
    """Recursively finds all specification files under a directory or validates a single file."""
    if target.is_file():
        return [target] if is_specification_file(target) else []
    files: list[Path] = []
    for p in sorted(target.rglob("*.md")):
        if is_specification_file(p):
            files.append(p)
    return files


def validate_specifications(
    root_dir: Path, target_path: Path | None = None
) -> tuple[bool, list[SchemaDiagnosticError], int]:
    """Audits specification files against schema v2.0.

    Returns (is_valid, all_errors, total_audited_count).
    """
    target = target_path if target_path is not None else (root_dir / "docs" / "project")
    if not target.exists():
        return True, [], 0

    spec_files = collect_specification_files(target)
    all_errors: list[SchemaDiagnosticError] = []

    for file_path in spec_files:
        try:
            content = file_path.read_text(encoding="utf-8")
        except OSError as os_err:
            all_errors.append(
                SchemaDiagnosticError(
                    file_path=str(file_path),
                    line=1,
                    column=1,
                    message=f"Could not read file: {os_err}",
                )
            )
            continue

        errors = validate_document(content, file_path=file_path)
        all_errors.extend(errors)

    return len(all_errors) == 0, all_errors, len(spec_files)
