"""Architecture profiles and baseline ADR data models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ..config.models import SliceConfig


@dataclass
class BaselineADR:
    number: int
    slug: str
    title: str
    status: str = "Accepted"
    date: str = "2026-09-29"
    content: str = ""

    @property
    def filename(self) -> str:
        return f"adr-{self.number:04d}-{self.slug}.md"

    @property
    def canonical_id(self) -> str:
        return f"ADR-{self.number:04d}"


@dataclass
class Profile:
    id: str
    name: str
    description: str
    version: str = "0.1.0"
    extends: list[str] = field(default_factory=list)
    adrs: list[BaselineADR] = field(default_factory=list)
    slices: list[SliceConfig] = field(default_factory=list)
    overrides: dict[str, Any] = field(default_factory=dict)
    invariants: list[str] = field(default_factory=list)
    rules: list[str] = field(default_factory=list)


class ProfileError(Exception):
    """Base exception for profile operations."""


class ProfileInheritanceError(ProfileError):
    """Raised when circular inheritance or inheritance graph resolution fails."""


class ADRCollisionError(ProfileError):
    """Raised when duplicate or conflicting baseline ADR numbers occur."""
