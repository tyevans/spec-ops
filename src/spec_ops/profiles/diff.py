"""Semantic invariant, baseline ADR, and configuration diff engine for architectural profiles."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .models import BaselineADR, Profile


@dataclass
class ADRDiff:
    canonical_id: str
    slug: str
    title: str
    change_type: str  # "added", "removed", "modified"
    source_title: str | None = None
    target_title: str | None = None
    content_changed: bool = False


@dataclass
class InvariantDiff:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)


@dataclass
class ConfigDiff:
    file_length_limit: tuple[int, int] | None = None
    require_mutation_testing: tuple[bool, bool] | None = None
    other_changes: dict[str, tuple[Any, Any]] = field(default_factory=dict)


@dataclass
class ProfileSemanticDiff:
    source_id: str
    source_version: str
    target_id: str
    target_version: str
    adrs: list[ADRDiff] = field(default_factory=list)
    invariants: InvariantDiff = field(default_factory=InvariantDiff)
    config: ConfigDiff = field(default_factory=ConfigDiff)
    breaking_changes: list[str] = field(default_factory=list)

    @property
    def is_breaking(self) -> bool:
        return len(self.breaking_changes) > 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": f"{self.source_id}@{self.source_version}",
            "target": f"{self.target_id}@{self.target_version}",
            "is_breaking": self.is_breaking,
            "breaking_changes": list(self.breaking_changes),
            "adrs": [
                {
                    "id": a.canonical_id,
                    "slug": a.slug,
                    "title": a.title,
                    "change_type": a.change_type,
                    "source_title": a.source_title,
                    "target_title": a.target_title,
                    "content_changed": a.content_changed,
                }
                for a in self.adrs
            ],
            "invariants": {
                "added": list(self.invariants.added),
                "removed": list(self.invariants.removed),
            },
            "configuration": {
                "file_length_limit": {
                    "source": self.config.file_length_limit[0] if self.config.file_length_limit else None,
                    "target": self.config.file_length_limit[1] if self.config.file_length_limit else None,
                },
                "require_mutation_testing": {
                    "source": self.config.require_mutation_testing[0] if self.config.require_mutation_testing else None,
                    "target": self.config.require_mutation_testing[1] if self.config.require_mutation_testing else None,
                },
                "other": dict(self.config.other_changes),
            },
        }

    def render_text(self) -> str:
        lines: list[str] = [
            f"=== SpecOps Profile Semantic Diff: {self.source_id}@{self.source_version} -> {self.target_id}@{self.target_version} ==="
        ]

        if self.breaking_changes:
            lines.append(f"\n⚠️  BREAKING CHANGES ({len(self.breaking_changes)}):")
            for bc in self.breaking_changes:
                lines.append(f"  • {bc}")

        added_adrs = [a for a in self.adrs if a.change_type == "added"]
        removed_adrs = [a for a in self.adrs if a.change_type == "removed"]
        modified_adrs = [a for a in self.adrs if a.change_type == "modified"]

        lines.append("\n📋 Baseline ADRs:")
        if not self.adrs:
            lines.append("  (no changes)")
        else:
            for a in added_adrs:
                lines.append(f"  + Added {a.canonical_id}: {a.title}")
            for a in modified_adrs:
                lines.append(f"  ~ Modified {a.canonical_id}: {a.title}")
            for a in removed_adrs:
                lines.append(f"  - Deprecated/Removed {a.canonical_id}: {a.title}")

        lines.append("\n🛡️  Invariant Rules:")
        if not self.invariants.added and not self.invariants.removed:
            lines.append("  (no changes)")
        else:
            for inv in self.invariants.added:
                lines.append(f"  + Added: {inv}")
            for inv in self.invariants.removed:
                lines.append(f"  - Removed: {inv}")

        lines.append("\n⚙️  Configuration & Limits:")
        has_cfg = False
        if self.config.file_length_limit:
            has_cfg = True
            old_lim, new_lim = self.config.file_length_limit
            lines.append(f"  ~ file_length_limit: {old_lim} -> {new_lim}")
        if self.config.require_mutation_testing:
            has_cfg = True
            old_m, new_m = self.config.require_mutation_testing
            lines.append(f"  ~ quality.require_mutation_testing: {str(old_m).lower()} -> {str(new_m).lower()}")
        if not has_cfg:
            lines.append("  (no changes)")

        return "\n".join(lines)


def _extract_file_limit(prof: Any) -> int:
    limit = getattr(prof, "file_length_limit", None)
    if isinstance(limit, int):
        return limit
    overrides = getattr(prof, "overrides", {})
    if isinstance(overrides, dict):
        arch = overrides.get("architecture", {})
        if isinstance(arch, dict) and "file_length_limit" in arch:
            try:
                return int(arch["file_length_limit"])
            except (ValueError, TypeError):
                pass
    return 500


def _extract_mutation_testing(prof: Any) -> bool:
    overrides = getattr(prof, "overrides", {})
    if isinstance(overrides, dict):
        quality = overrides.get("quality", {})
        if isinstance(quality, dict):
            return bool(quality.get("require_mutation_testing", False))
    return False


def compute_profile_diff(source: Any, target: Any) -> ProfileSemanticDiff:
    """Computes a semantic difference between two architectural profiles or compositions."""
    s_id = getattr(source, "id", None) or (source.profile_ids[0] if getattr(source, "profile_ids", None) else "source")
    t_id = getattr(target, "id", None) or (target.profile_ids[0] if getattr(target, "profile_ids", None) else "target")
    s_ver = getattr(source, "version", "0.1.0")
    t_ver = getattr(target, "version", "0.1.0")

    breaking_changes: list[str] = []

    # ADR Diff
    source_adrs = getattr(source, "adrs", [])
    target_adrs = getattr(target, "adrs", [])

    source_by_slug = {a.slug: a for a in source_adrs}
    target_by_slug = {a.slug: a for a in target_adrs}

    adr_diffs: list[ADRDiff] = []

    for a in target_adrs:
        if a.slug not in source_by_slug:
            adr_diffs.append(
                ADRDiff(
                    canonical_id=a.canonical_id,
                    slug=a.slug,
                    title=a.title,
                    change_type="added",
                    target_title=a.title,
                )
            )
        else:
            s_adr = source_by_slug[a.slug]
            s_body = s_adr.content.strip()
            t_body = a.content.strip()
            content_changed = s_body != t_body
            title_changed = s_adr.title != a.title
            if content_changed or title_changed:
                adr_diffs.append(
                    ADRDiff(
                        canonical_id=a.canonical_id,
                        slug=a.slug,
                        title=a.title,
                        change_type="modified",
                        source_title=s_adr.title,
                        target_title=a.title,
                        content_changed=content_changed,
                    )
                )

    for a in source_adrs:
        if a.slug not in target_by_slug:
            adr_diffs.append(
                ADRDiff(
                    canonical_id=a.canonical_id,
                    slug=a.slug,
                    title=a.title,
                    change_type="removed",
                    source_title=a.title,
                )
            )
            breaking_changes.append(f"Deprecated/removed baseline ADR: {a.canonical_id} ({a.title})")

    # Invariants Diff (deterministic and commutative with respect to order)
    s_inv_set = set(getattr(source, "invariants", []))
    t_inv_set = set(getattr(target, "invariants", []))

    added_invs = sorted(t_inv_set - s_inv_set)
    removed_invs = sorted(s_inv_set - t_inv_set)
    inv_diff = InvariantDiff(added=added_invs, removed=removed_invs)

    # Config & Limits Diff
    s_limit = _extract_file_limit(source)
    t_limit = _extract_file_limit(target)
    file_diff: tuple[int, int] | None = None
    if s_limit != t_limit:
        file_diff = (s_limit, t_limit)
        if t_limit < s_limit:
            breaking_changes.append(f"Decreased file length limit from {s_limit} to {t_limit} lines")

    s_mut = _extract_mutation_testing(source)
    t_mut = _extract_mutation_testing(target)
    mut_diff: tuple[bool, bool] | None = None
    if s_mut != t_mut:
        mut_diff = (s_mut, t_mut)
        if not s_mut and t_mut:
            breaking_changes.append("Newly mandated mutation testing (quality.require_mutation_testing = true)")

    config_diff = ConfigDiff(
        file_length_limit=file_diff,
        require_mutation_testing=mut_diff,
    )

    return ProfileSemanticDiff(
        source_id=s_id,
        source_version=s_ver,
        target_id=t_id,
        target_version=t_ver,
        adrs=adr_diffs,
        invariants=inv_diff,
        config=config_diff,
        breaking_changes=breaking_changes,
    )
