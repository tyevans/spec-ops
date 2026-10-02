"""Subagent orchestration guidelines, spec consultation validation, and peer coordination protocol."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from .parser import extract_frontmatter


@dataclass
class ConsultedSpecReference:
    """Represents a version-locked specification consulted by a subagent."""

    spec_type: str  # "persona", "prd", "story", "adr", "backlog"
    identifier: str
    path: str = ""
    title: str = ""
    status: str = "Accepted"
    invariants_or_outcomes: list[str] = field(default_factory=list)
    is_valid: bool = True
    error_message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubagentConsultationRequest:
    """Represents a structured inter-subagent peer consultation request."""

    sender_role: str
    recipient_role: str
    phase: str
    task_id: str = ""
    target_bc: str = "core"
    consulted_specs: list[ConsultedSpecReference] = field(default_factory=list)
    changed_files: list[str] = field(default_factory=list)
    inquiry_type: str = "peer_review"  # "peer_review", "contract_clarification", "seam_validation", "phase_handoff", "execution_report"
    query: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class SubagentConsultationResponse:
    """Represents the outcome of an inter-subagent peer consultation."""

    approved: bool
    feedback: list[str] = field(default_factory=list)
    seam_violations: list[str] = field(default_factory=list)
    adr_violations: list[str] = field(default_factory=list)
    missing_specs: list[str] = field(default_factory=list)
    execution_state: str = "PENDING"  # "APPROVED", "BLOCKED", "NEEDS_REVISION", "COMPLETED"
    guidance: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SpecConsultationValidator:
    """Validates that subagents properly consult living specifications in docs/project/ and follow peer protocols."""

    MANDATORY_HIERARCHY: tuple[str, ...] = ("persona", "prd", "story", "adr", "backlog")

    @staticmethod
    def _extract_digits(identifier: str) -> str:
        digits = re.sub(r"[^\d]", "", identifier)
        return digits.lstrip("0") if digits else ""

    @classmethod
    def resolve_spec_file(cls, repo_root: Path, spec_type: str, identifier: str) -> Path | None:
        """Locates an approved spec file in docs/project/ for a given type and identifier."""
        type_dir_map = {
            "persona": repo_root / "docs" / "project" / "user_stories",
            "prd": repo_root / "docs" / "project" / "product",
            "story": repo_root / "docs" / "project" / "user_stories",
            "adr": repo_root / "docs" / "project" / "adrs",
            "backlog": repo_root / "docs" / "project" / "backlog",
        }
        target_dir = type_dir_map.get(spec_type.lower())
        if not target_dir or not target_dir.exists():
            return None

        if spec_type.lower() == "persona":
            p = target_dir / "PERSONAS.md"
            return p if p.exists() else None

        num = cls._extract_digits(identifier)
        if not num:
            return None

        prefix_map = {"prd": "prd", "story": "us", "adr": "adr", "backlog": ""}
        prefix = prefix_map.get(spec_type.lower(), "")

        for f in target_dir.rglob("*.md"):
            if f.name.startswith("REGISTRY"):
                continue
            m = re.search(rf"(?:{prefix})?[-_]?(\d+)", f.stem, re.IGNORECASE)
            if m and cls._extract_digits(m.group(1)) == num:
                return f
        return None

    @classmethod
    def verify_spec_reference(cls, repo_root: Path, ref: ConsultedSpecReference) -> ConsultedSpecReference:
        """Inspects disk to verify a consulted spec reference exists, is accepted, and captures invariants."""
        found = cls.resolve_spec_file(repo_root, ref.spec_type, ref.identifier)
        if not found or not found.exists():
            ref.is_valid = False
            ref.error_message = f"Specification '{ref.identifier}' not found under docs/project/{ref.spec_type}."
            return ref

        ref.path = str(found.relative_to(repo_root))
        try:
            content = found.read_text(encoding="utf-8", errors="replace")
            meta, body = extract_frontmatter(content)
            ref.title = meta.get("title") or found.stem
            status = meta.get("status") or meta.get("stage") or "Accepted"
            ref.status = str(status)

            if ref.spec_type.lower() == "adr":
                invs = [
                    ln.strip().lstrip("-* ").strip()
                    for ln in body.splitlines()
                    if (ln.strip().startswith("- ") or ln.strip().startswith("* "))
                    and any(k in ln.lower() for k in ("limit", "invariant", "must", "strictly", "mock", "tdd"))
                ]
                ref.invariants_or_outcomes = invs[:5]
            elif ref.spec_type.lower() == "prd":
                outcomes = [
                    ln.strip().lstrip("-* ").strip()
                    for ln in body.splitlines()
                    if (ln.strip().startswith("- ") or ln.strip().startswith("* "))
                    and "outcome" in body[: body.find(ln)].lower()[-200:]
                ]
                ref.invariants_or_outcomes = outcomes[:6]
            elif ref.spec_type.lower() == "story":
                scenarios = [m.group(1).strip() for m in re.finditer(r"Scenario:\s*(.+)", body)]
                ref.invariants_or_outcomes = scenarios[:6]

            ref.is_valid = True
            ref.error_message = ""
        except Exception as exc:
            ref.is_valid = False
            ref.error_message = f"Failed to parse specification '{found}': {exc}"

        return ref

    @classmethod
    def evaluate_peer_consultation(
        cls,
        request: SubagentConsultationRequest,
        repo_root: Path | None = None,
    ) -> SubagentConsultationResponse:
        """Evaluates an inter-subagent peer consultation request against ADR invariants and seam boundaries."""
        seam_violations: list[str] = []
        adr_violations: list[str] = []
        missing_specs: list[str] = []
        feedback: list[str] = []

        if not request.consulted_specs:
            missing_specs.append("No approved specifications in 'docs/project/' were consulted before requesting review.")
            feedback.append("Consult governing ADRs, PRDs, and user stories in 'docs/project/' to anchor changes.")

        if repo_root:
            for spec in request.consulted_specs:
                cls.verify_spec_reference(repo_root, spec)
                if not spec.is_valid:
                    missing_specs.append(spec.error_message)
                    feedback.append(f"Unresolved specification reference: {spec.identifier}")

        target_bc = (request.target_bc or "core").strip().lower()

        for rel in request.changed_files:
            rel_norm = rel.replace("\\", "/")
            if rel_norm.startswith("docs/project/backlog/"):
                adr_violations.append(f"ADR-0005: Forbidden backlog modification on feature branch: {rel_norm}")
                feedback.append(f"Discard changes to {rel_norm}. Backlog files must never be modified on task branches.")

            if rel_norm.startswith("src/spec_ops/"):
                parts = rel_norm[len("src/spec_ops/") :].split("/")
                if parts and parts[0] not in ("core", "config", "cli", target_bc, "__init__.py"):
                    seam_violations.append(
                        f"Boundary seam crossing: file '{rel_norm}' belongs to '{parts[0]}' BC while task targets '{target_bc}'"
                    )
                    feedback.append(f"Coordinate with lead orchestrator or review interface contract between '{target_bc}' and '{parts[0]}'.")

        approved = (len(seam_violations) == 0 and len(adr_violations) == 0 and len(missing_specs) == 0)
        execution_state = "APPROVED" if approved else ("BLOCKED" if adr_violations else "NEEDS_REVISION")

        guidance = (
            "Peer consultation approved. All bounded context seams and consulted specifications are verified."
            if approved
            else f"Peer consultation blocked or needs revision: {len(adr_violations)} ADR violation(s), "
            f"{len(seam_violations)} seam violation(s), {len(missing_specs)} missing spec(s)."
        )

        return SubagentConsultationResponse(
            approved=approved,
            feedback=feedback,
            seam_violations=seam_violations,
            adr_violations=adr_violations,
            missing_specs=missing_specs,
            execution_state=execution_state,
            guidance=guidance,
        )

    @classmethod
    def format_consultation_brief(cls, request: SubagentConsultationRequest) -> str:
        """Renders a readable summary brief of the peer consultation and consulted specs."""
        lines = [
            f"# Multi-Agent Consultation Brief: {request.task_id or 'General'}",
            f"**Sender**: {request.sender_role} -> **Recipient**: {request.recipient_role}",
            f"**Phase**: {request.phase} | **Target BC**: {request.target_bc}",
            f"**Inquiry Type**: {request.inquiry_type}",
            "\n## Consulted Specifications (`docs/project/`)",
        ]
        if not request.consulted_specs:
            lines.append("*(None provided)*")
        else:
            for spec in request.consulted_specs:
                status_suffix = f" [{spec.status}]" if spec.status else ""
                lines.append(f"- **{spec.identifier}** ({spec.spec_type}){status_suffix}: {spec.title}")
                for item in spec.invariants_or_outcomes:
                    lines.append(f"  - {item}")

        if request.changed_files:
            lines.append("\n## Changed Files")
            for f in request.changed_files:
                lines.append(f"- `{f}`")

        if request.query:
            lines.append(f"\n## Specific Inquiry\n{request.query}")

        return "\n".join(lines)
