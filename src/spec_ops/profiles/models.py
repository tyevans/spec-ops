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
    adrs: list[BaselineADR] = field(default_factory=list)
    slices: list[SliceConfig] = field(default_factory=list)
