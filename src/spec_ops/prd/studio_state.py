"""PRD Studio domain model and reactive state manager for web-based authoring."""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from ..config.loader import load_config
from ..core.parser import extract_frontmatter
from .lifecycle import PRDLifecycleManager
from .studio import (
    commit_prd_specification,
    create_prd_draft,
    serialize_prd_document,
    validate_prd_schema,
)


@dataclass
class PRDSummary:
    """Lightweight metadata descriptor for listed PRD specifications."""

    prd_id: str
    title: str
    stage: str
    persona: str
    component: str
    file_path: str
    outcomes_count: int


@dataclass
class PRDStudioSessionState:
    """In-memory session state representing active PRD Studio editor buffer."""

    session_id: str = field(default_factory=lambda: f"studio-{uuid.uuid4().hex[:8]}")
    active_prd_id: str | None = None
    active_file_path: str | None = None
    stage: str = "idea"
    title: str = ""
    persona: str = ""
    component: str = "core"
    problem_statement: str = ""
    outcomes: list[str] = field(default_factory=list)
    is_dirty: bool = False
    is_valid: bool = False
    validation_errors: list[str] = field(default_factory=list)
    last_saved_at: float | None = None
    last_commit_hash: str | None = None
    open_browser: bool = False
    host: str = "127.0.0.1"
    port: int = 8080


class PRDStudioStateManager:
    """Coordinates lifecycle state transitions, draft synchronization, and git writebacks."""

    VALID_STAGES: tuple[str, ...] = ("idea", "shaped", "accepted", "shipped")

    def __init__(
        self,
        repo_root: Path | str,
        session_id: str | None = None,
        open_browser: bool = False,
        host: str = "127.0.0.1",
        port: int = 8080,
    ) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.state = PRDStudioSessionState(
            session_id=session_id or f"studio-{uuid.uuid4().hex[:8]}",
            open_browser=open_browser,
            host=host,
            port=port,
        )
        self._sync_validation()

    @property
    def product_dir(self) -> Path:
        return self.repo_root / "docs" / "project" / "product"

    def _sync_validation(self) -> tuple[bool, list[str]]:
        data = {
            "title": self.state.title,
            "persona": self.state.persona,
            "problem_statement": self.state.problem_statement,
            "outcomes": self.state.outcomes,
        }
        is_valid, errors = validate_prd_schema(data)
        self.state.is_valid = is_valid
        self.state.validation_errors = errors
        return is_valid, errors

    def new_draft(
        self,
        title: str = "",
        persona: str = "",
        component: str = "core",
        problem_statement: str = "",
        outcomes: list[str] | None = None,
    ) -> PRDStudioSessionState:
        """Resets the editor session with a blank or seeded draft."""
        self.state.active_prd_id = None
        self.state.active_file_path = None
        self.state.stage = "idea"
        self.state.title = title
        self.state.persona = persona
        self.state.component = component
        self.state.problem_statement = problem_statement
        self.state.outcomes = list(outcomes) if outcomes else []
        self.state.is_dirty = bool(title or persona or problem_statement or outcomes)
        self._sync_validation()
        return self.state

    def update_field(self, field_name: str, value: Any) -> tuple[bool, list[str]]:
        """Updates a single draft field and re-computes validation invariants."""
        if field_name == "title":
            self.state.title = str(value)
        elif field_name in ("persona", "target_persona"):
            self.state.persona = str(value)
        elif field_name == "component":
            self.state.component = str(value) or "core"
        elif field_name == "problem_statement":
            self.state.problem_statement = str(value)
        elif field_name == "outcomes":
            if isinstance(value, list):
                self.state.outcomes = [str(item) for item in value]
            elif isinstance(value, str):
                self.state.outcomes = [line.strip("- ").strip() for line in value.splitlines() if line.strip("- ").strip()]
        elif field_name == "stage":
            val = str(value).lower()
            if val in self.VALID_STAGES:
                self.state.stage = val
        else:
            raise KeyError(f"Unknown studio draft field: {field_name}")

        self.state.is_dirty = True
        return self._sync_validation()

    def add_outcome(self, outcome_text: str) -> tuple[bool, list[str]]:
        """Appends a new checkable outcome to the draft."""
        clean = outcome_text.strip().lstrip("-").strip()
        if clean:
            self.state.outcomes.append(clean)
            self.state.is_dirty = True
        return self._sync_validation()

    def remove_outcome(self, index: int) -> bool:
        """Removes a checkable outcome by index."""
        if 0 <= index < len(self.state.outcomes):
            self.state.outcomes.pop(index)
            self.state.is_dirty = True
            self._sync_validation()
            return True
        return False

    def reorder_outcomes(self, new_order: list[int]) -> bool:
        """Permutes checkable outcomes according to specified index sequence."""
        if sorted(new_order) == list(range(len(self.state.outcomes))):
            self.state.outcomes = [self.state.outcomes[i] for i in new_order]
            self.state.is_dirty = True
            return True
        return False

    def list_prds(self) -> list[PRDSummary]:
        """Lists all existing PRDs across lifecycle stages."""
        summaries: list[PRDSummary] = []
        if not self.product_dir.exists():
            return summaries

        for stage in self.VALID_STAGES:
            stage_dir = self.product_dir / stage
            if not stage_dir.exists():
                continue
            for file_path in sorted(stage_dir.glob("*.md")):
                if file_path.name == "REGISTRY.md":
                    continue
                meta, body = extract_frontmatter(file_path.read_text(encoding="utf-8"))
                outcomes: list[str] = []
                in_outcomes = False
                for line in body.splitlines():
                    if line.startswith("## Checkable Outcomes"):
                        in_outcomes = True
                        continue
                    if in_outcomes and line.startswith("## "):
                        break
                    if in_outcomes and line.strip().startswith("- "):
                        outcomes.append(line.strip()[2:].strip())

                summaries.append(
                    PRDSummary(
                        prd_id=str(meta.get("id", file_path.stem)),
                        title=str(meta.get("title", "")),
                        stage=stage,
                        persona=str(meta.get("target_persona", meta.get("persona", ""))),
                        component=str(meta.get("component", "core")),
                        file_path=str(file_path.relative_to(self.repo_root)),
                        outcomes_count=len(outcomes),
                    )
                )
        return summaries

    def load_prd(self, prd_id_or_path: str | Path) -> bool:
        """Loads an existing PRD specification into the session editor buffer."""
        target_path: Path | None = None
        candidate = Path(prd_id_or_path)
        if candidate.is_file():
            target_path = candidate.resolve()
        elif self.product_dir.exists():
            raw = str(prd_id_or_path).strip().upper()
            clean = raw if raw.startswith("PRD-") else f"PRD-{raw.zfill(4)}"
            for f in self.product_dir.rglob("*.md"):
                if f.name == "REGISTRY.md":
                    continue
                if clean.lower() in f.stem.lower() or f.stem.upper().endswith(clean):
                    target_path = f.resolve()
                    break
                meta, _ = extract_frontmatter(f.read_text(encoding="utf-8"))
                if str(meta.get("id", "")).strip().upper() in (clean, clean.replace("PRD-", "")):
                    target_path = f.resolve()
                    break

        if not target_path or not target_path.exists():
            return False

        meta, body = extract_frontmatter(target_path.read_text(encoding="utf-8"))
        prob_statement, outcomes = "", []
        in_problem, in_outcomes = False, False

        for line in body.splitlines():
            if line.startswith("## Problem Statement"):
                in_problem, in_outcomes = True, False
                continue
            if line.startswith("## Checkable Outcomes"):
                in_problem, in_outcomes = False, True
                continue
            if line.startswith("## "):
                in_problem, in_outcomes = False, False
                continue
            if in_problem:
                prob_statement += line + "\n"
            elif in_outcomes and line.strip().startswith("- "):
                outcomes.append(line.strip()[2:].strip())

        stage = target_path.parent.name.lower()
        self.state.active_prd_id = str(meta.get("id", ""))
        self.state.active_file_path = str(target_path.relative_to(self.repo_root))
        self.state.stage = stage if stage in self.VALID_STAGES else "idea"
        self.state.title = str(meta.get("title", ""))
        self.state.persona = str(meta.get("target_persona", meta.get("persona", "")))
        self.state.component = str(meta.get("component", "core"))
        self.state.problem_statement = prob_statement.strip()
        self.state.outcomes = outcomes
        self.state.is_dirty = False
        self._sync_validation()
        return True

    def save_draft(self) -> dict[str, Any]:
        """Saves editor buffer to disk, updating existing file or creating a new idea draft."""
        is_valid, violations = self._sync_validation()
        if not is_valid:
            return {"success": False, "error": "Validation Error (ADR-0001)", "violations": violations}

        if not self.state.active_file_path:
            res = create_prd_draft(
                self.repo_root,
                {
                    "title": self.state.title,
                    "persona": self.state.persona,
                    "component": self.state.component,
                    "problem_statement": self.state.problem_statement,
                    "outcomes": self.state.outcomes,
                },
            )
            if res.get("success"):
                self.state.active_prd_id = res["prd_id"]
                self.state.active_file_path = res["file_path"]
                self.state.is_dirty = False
                self.state.last_saved_at = time.time()
            return res

        target_path = self.repo_root / self.state.active_file_path
        frontmatter = {
            "id": self.state.active_prd_id,
            "title": self.state.title,
            "status": self.state.stage.capitalize(),
            "target_persona": self.state.persona,
            "component": self.state.component,
        }
        outcomes_formatted = "\n".join(f"- {o}" for o in self.state.outcomes)
        body = (
            f"# {self.state.active_prd_id}: {self.state.title}\n\n"
            f"## Problem Statement\n{self.state.problem_statement}\n\n"
            f"## Checkable Outcomes\n{outcomes_formatted}\n"
        )
        target_path.write_text(serialize_prd_document(frontmatter, body), encoding="utf-8")
        self.state.is_dirty = False
        self.state.last_saved_at = time.time()
        return {"success": True, "prd_id": self.state.active_prd_id, "file_path": self.state.active_file_path}

    def commit_changes(
        self,
        commit_message: str | None = None,
        author_name: str = "Taylor",
        author_email: str = "taylor@specops.local",
    ) -> dict[str, Any]:
        """Saves current state and commits directly to active git feature branch."""
        save_res = self.save_draft()
        if not save_res.get("success"):
            return save_res

        assert self.state.active_file_path is not None
        target_path = self.repo_root / self.state.active_file_path
        content = target_path.read_text(encoding="utf-8")
        msg = commit_message or f"spec(prd): update {self.state.active_prd_id or 'specification'}"
        commit_res = commit_prd_specification(
            self.repo_root,
            self.state.active_file_path,
            content,
            commit_message=msg,
            author_name=author_name,
            author_email=author_email,
        )
        if commit_res.get("success"):
            self.state.last_commit_hash = commit_res.get("commit_hash")
        return commit_res

    def promote_stage(self, target_stage: str) -> dict[str, Any]:
        """Promotes active PRD to target lifecycle stage using PRDLifecycleManager."""
        clean_stage = target_stage.lower()
        if clean_stage not in self.VALID_STAGES:
            return {"success": False, "error": f"Invalid stage: {target_stage}"}
        if not self.state.active_file_path or not self.state.active_prd_id:
            return {"success": False, "error": "No active PRD loaded to promote"}

        self.save_draft()
        config = load_config(root_dir=self.repo_root)
        mgr = PRDLifecycleManager(config)
        ok, msg = mgr.promote(self.state.active_prd_id, clean_stage)
        if ok:
            self.state.stage = clean_stage
            new_file = mgr.find_prd_file(self.state.active_prd_id)
            if new_file:
                self.state.active_file_path = str(new_file.relative_to(self.repo_root))
            return {"success": True, "message": msg, "stage": clean_stage, "file_path": self.state.active_file_path}
        return {"success": False, "error": msg}

    def to_dict(self) -> dict[str, Any]:
        """Serializes current studio state for web client transmission."""
        return asdict(self.state)
