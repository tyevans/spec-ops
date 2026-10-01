"""Universal core domain models for SpecOps Project Management as Code."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Persona:
    id: str
    name: str
    role: str = ""
    pain_points: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)
    features: list[str] = field(default_factory=list)
    story_ids: list[str] = field(default_factory=list)
    quote: str = ""
    raw_markdown: str = ""
    file_path: Path | None = None


@dataclass
class UserStory:
    id: str
    title: str
    status: str = "Accepted"
    persona: str = ""
    feature: str = ""
    governing_prd: str = ""
    as_a: str = ""
    i_want: str = ""
    so_that: str = ""
    scenarios: list[str] = field(default_factory=list)
    implementing_tasks: list[str] = field(default_factory=list)
    raw_markdown: str = ""
    file_path: Path | None = None


@dataclass
class PRD:
    id: str
    title: str
    status: str = "Accepted"
    target_persona: str = ""
    problem_statement: str = ""
    outcomes: list[str] = field(default_factory=list)
    linked_stories: list[str] = field(default_factory=list)
    implementing_tasks: list[str] = field(default_factory=list)
    raw_markdown: str = ""
    file_path: Path | None = None


@dataclass
class BlockerInfo:
    type: str = "unknown"  # unknown, spike_needed, external, dependency
    question: str = ""
    raised_by: str = ""
    raised_at: str = ""
    spike_id: str = ""
    resolution: str = ""
    resolved_at: str = ""
    adr_id: str = ""


@dataclass
class Task:
    id: str
    title: str
    status: str = "Proposed"  # Proposed, Refined, Complete, In-Progress, Review, Blocked
    dependencies: list[str] = field(default_factory=list)
    governing_adrs: list[str] = field(default_factory=list)
    governing_prds: list[str] = field(default_factory=list)
    governing_stories: list[str] = field(default_factory=list)
    target_bc: str = ""
    target_release: str = ""
    prs: list[str] = field(default_factory=list)
    pr_url: str = ""
    claimed_by: str = ""
    branch: str = ""
    priority_rank: int = 999999
    body: str = ""
    raw_markdown: str = ""
    file_path: Path = field(default_factory=Path)
    commits: list[CommitInfo] = field(default_factory=list)
    allows_dependencies: bool = False
    hypothesis: str = ""
    timebox: str = ""
    signed_off_by: str = ""
    signed_off_at: str = ""
    has_signed_commits: bool | None = None
    commit_signature_status: str = ""
    blocker: BlockerInfo | None = None
    slice_type: str = "feat"
    unblocked: bool = False
    failure_history: list[dict[str, Any]] = field(default_factory=list)
    completed_at: str = ""
    claimed_at: str = ""
    timestamp: str = ""
    pinned: bool = False
    priority_pin: int | None = None

    @property
    def canonical_id(self) -> str:
        clean = self.id.replace("TASK-", "").replace("SPIKE-", "").lstrip("0")
        prefix = "SPIKE-" if str(self.id).upper().startswith("SPIKE") else "TASK-"
        return f"{prefix}{clean.zfill(4)}" if clean else self.id

    @property
    def slug(self) -> str:
        clean = "".join(c if c.isalnum() else "-" for c in self.title.lower()).strip("-")
        clean_id = self.canonical_id.lower().replace("task-", "").replace("spike-", "")
        return f"{clean_id}-{clean[:40]}"


@dataclass
class ADR:
    id: str
    title: str
    status: str = "Accepted"
    domain: str = ""
    context: str = ""
    decision: str = ""
    consequences: str = ""
    implementing_tasks: list[str] = field(default_factory=list)
    raw_markdown: str = ""
    file_path: Path | None = None


@dataclass
class CommitInfo:
    hash: str
    author: str
    date: str
    subject: str
    prs: list[str] = field(default_factory=list)
    signature_status: str = ""
    is_signed: bool = False
    provenance: str = ""
    trailers: dict[str, str] = field(default_factory=dict)


@dataclass
class TraceabilityEdge:
    source_type: str
    source_id: str
    target_type: str
    target_id: str
    relation: str  # desires, specifies, implements, governed_by, deploys_to, depends_on


@dataclass
class GraphNode:
    id: str
    label: str
    type: str  # persona, story, prd, task, adr, bc
    color: str
    status: str = ""
    role: str = ""
    domain: str = ""
    bc: str = ""
    prs: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GraphEdge:
    source: str
    target: str
    relation: str
    source_type: str
    target_type: str


@dataclass
class GraphData:
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)


@dataclass
class ProjectData:
    personas: list[Persona] = field(default_factory=list)
    stories: list[UserStory] = field(default_factory=list)
    prds: list[PRD] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    adrs: list[ADR] = field(default_factory=list)
    edges: list[TraceabilityEdge] = field(default_factory=list)
    health_metrics: dict[str, Any] = field(default_factory=dict)
