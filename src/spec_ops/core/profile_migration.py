"""Living architecture profile migration engine and schema evolvability validator.

Governed by ADR-0001, ADR-0002, ADR-0003, ADR-0007, and PRD-0005.
Deals strictly with public domain contracts and keeps source under 400 lines.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any

import yaml


@dataclass
class ProfileMigrationReport:
    """Encapsulates profile migration execution results and schema diff details."""

    from_version: str
    to_version: str
    is_up_to_date: bool
    applied_steps: list[str] = field(default_factory=list)
    changes: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializes report into JSON-compatible dictionary."""
        return {
            "from_version": self.from_version,
            "to_version": self.to_version,
            "is_up_to_date": self.is_up_to_date,
            "applied_steps": list(self.applied_steps),
            "changes": list(self.changes),
            "warnings": list(self.warnings),
        }

    def summary(self) -> str:
        """Renders human-readable summary of migration status."""
        if self.is_up_to_date:
            return f"Profile configuration is up to date (schema version {self.to_version})."
        return (
            f"Migrated profile from schema {self.from_version} to {self.to_version} "
            f"({len(self.changes)} change(s), {len(self.applied_steps)} step(s))."
        )


class ProfileMigrator:
    """Validates and migrates architectural profile schema configurations."""

    CURRENT_SCHEMA_VERSION = "2.0.0"

    def detect_version(self, data: dict[str, Any]) -> str:
        """Inspects profile configuration dictionary and detects semantic schema version."""
        if not isinstance(data, dict):
            return "1.0.0"

        raw_ver = data.get("schema_version") or data.get("version")
        if raw_ver is not None:
            v_str = str(raw_ver).strip().lstrip("vV")
            if v_str.startswith("2"):
                return "2.0.0"
            if v_str.startswith("1"):
                return "1.0.0"
            return v_str

        if "profiles" in data and isinstance(data["profiles"], list):
            if "schema_version" in data:
                return "2.0.0"
        return "1.0.0"

    def validate_schema(self, data: dict[str, Any], version: str = "2.0.0") -> list[str]:
        """Validates configuration against targeted semantic schema specifications."""
        if not isinstance(data, dict):
            return ["Profile configuration must be a mapping dictionary"]

        errors: list[str] = []
        norm_ver = self._normalize_version_string(version)

        if norm_ver == "2.0.0":
            sv = data.get("schema_version") or data.get("version")
            if sv is None:
                errors.append("Missing required 'schema_version' field for schema 2.0.0")
            elif self.detect_version(data) != "2.0.0":
                errors.append(f"Incompatible schema version: expected '2.0.0', found '{sv}'")

            if "profiles" in data:
                if not isinstance(data["profiles"], list):
                    errors.append("'profiles' must be a list of profile identifiers")
                elif not all(isinstance(x, str) for x in data["profiles"]):
                    errors.append("All entries in 'profiles' must be strings")
            elif "profile" in data:
                if not isinstance(data["profile"], (str, list)):
                    errors.append("'profile' must be a string or list of strings")
            elif not any(k in data for k in ("id", "name")):
                errors.append("Profile configuration must specify 'profiles', 'profile', 'name', or 'id'")

            for list_key in ("invariants", "rules", "custom_rules", "rule_extensions", "slices"):
                if list_key in data and not isinstance(data[list_key], (list, dict)):
                    errors.append(f"'{list_key}' must be a sequence or mapping")

            for dict_key in ("overrides", "custom_overrides", "settings"):
                if dict_key in data and not isinstance(data[dict_key], dict):
                    errors.append(f"'{dict_key}' must be a dictionary mapping")
        else:
            if not any(k in data for k in ("profile", "profiles", "name", "id", "rules", "overrides")):
                errors.append("Legacy profile must define at least one profile name, rules, or overrides")
            if "overrides" in data and not isinstance(data["overrides"], dict):
                errors.append("'overrides' must be a dictionary mapping")

        return errors

    def migrate(
        self,
        profile_path: Path,
        target_version: str = "2.0.0",
        dry_run: bool = False,
    ) -> tuple[bool, ProfileMigrationReport]:
        """Applies forward non-destructive schema migrations to target profile configuration."""
        if not profile_path.exists():
            report = ProfileMigrationReport(
                from_version="unknown",
                to_version=target_version,
                is_up_to_date=False,
                warnings=[f"Profile file not found: {profile_path}"],
            )
            return False, report

        try:
            content = profile_path.read_text(encoding="utf-8")
        except Exception as err:
            report = ProfileMigrationReport(
                from_version="unknown",
                to_version=target_version,
                is_up_to_date=False,
                warnings=[f"Could not read profile file: {err}"],
            )
            return False, report

        has_frontmatter, raw_yaml, body, header_comments = self._split_content(content)

        try:
            data = yaml.safe_load(raw_yaml)
        except yaml.YAMLError as err:
            report = ProfileMigrationReport(
                from_version="unknown",
                to_version=target_version,
                is_up_to_date=False,
                warnings=[f"YAML parsing error: {err}"],
            )
            return False, report

        if data is None:
            data = {}
        elif not isinstance(data, dict):
            report = ProfileMigrationReport(
                from_version="unknown",
                to_version=target_version,
                is_up_to_date=False,
                warnings=["Profile configuration root must be a dictionary"],
            )
            return False, report

        current_ver = self.detect_version(data)
        norm_target = self._normalize_version_string(target_version)
        schema_errors = self.validate_schema(data, norm_target)

        if current_ver == norm_target and not schema_errors:
            report = ProfileMigrationReport(
                from_version=current_ver,
                to_version=norm_target,
                is_up_to_date=True,
                applied_steps=[],
                changes=[],
                warnings=[],
            )
            return True, report

        migrated_data = copy.deepcopy(data)
        applied_steps: list[str] = []
        changes: list[str] = []
        warnings: list[str] = []

        # 1. Upgrade schema version indicator
        if migrated_data.get("schema_version") != norm_target:
            old_sv = migrated_data.get("schema_version")
            migrated_data["schema_version"] = norm_target
            changes.append(f"Set schema_version: '{norm_target}' (was {repr(old_sv)})")
            applied_steps.append(f"Upgrade schema version to {norm_target}")

        if "version" in migrated_data and migrated_data["version"] != norm_target:
            old_v = migrated_data["version"]
            migrated_data["version"] = norm_target
            changes.append(f"Updated version: '{norm_target}' (was {repr(old_v)})")

        # 2. Canonicalize profile specification
        if "profile" in migrated_data:
            p_val = migrated_data["profile"]
            if isinstance(p_val, str):
                if "profiles" not in migrated_data:
                    migrated_data["profiles"] = [p_val]
                    changes.append(f"Normalized 'profile: {p_val}' to 'profiles: [{p_val}]'")
                    applied_steps.append("Convert scalar profile to profiles list")
                elif p_val not in migrated_data["profiles"]:
                    migrated_data["profiles"].insert(0, p_val)
                    changes.append(f"Appended profile '{p_val}' to profiles")
            elif isinstance(p_val, list):
                if "profiles" not in migrated_data:
                    migrated_data["profiles"] = list(p_val)
                    del migrated_data["profile"]
                    changes.append("Migrated 'profile' list to 'profiles'")
                    applied_steps.append("Normalize profiles key")
        elif "profiles" not in migrated_data:
            default_p = str(migrated_data.get("name") or migrated_data.get("id") or "core")
            migrated_data["profiles"] = [default_p]
            changes.append(f"Initialized profiles list: ['{default_p}']")
            applied_steps.append("Initialize profiles list")

        # 3. Consolidate legacy limits and quality settings into overrides
        self._consolidate_overrides(migrated_data, changes, applied_steps)

        # 4. Validate resulting target schema
        post_errors = self.validate_schema(migrated_data, norm_target)
        if post_errors:
            warnings.extend(post_errors)

        # 5. Persist migrated file
        if not dry_run:
            profile_path.parent.mkdir(parents=True, exist_ok=True)
            new_text = self._render_content(
                migrated_data,
                has_frontmatter=has_frontmatter,
                body=body,
                header_comments=header_comments,
            )
            profile_path.write_text(new_text, encoding="utf-8")

        report = ProfileMigrationReport(
            from_version=current_ver,
            to_version=norm_target,
            is_up_to_date=False,
            applied_steps=applied_steps,
            changes=changes,
            warnings=warnings,
        )
        return True, report

    def _normalize_version_string(self, ver: str) -> str:
        s = str(ver).strip().lstrip("vV")
        if s.startswith("2"):
            return "2.0.0"
        if s.startswith("1"):
            return "1.0.0"
        return s

    def _consolidate_overrides(
        self,
        data: dict[str, Any],
        changes: list[str],
        applied_steps: list[str],
    ) -> None:
        limit = None
        for key in ("file_length_limit", "max_file_lines", "file_limit"):
            if key in data:
                try:
                    limit = int(data[key])
                except (ValueError, TypeError):
                    limit = data[key]
                break

        if limit is not None:
            if "overrides" not in data or not isinstance(data["overrides"], dict):
                data["overrides"] = {}
            if "file_length_limit" not in data["overrides"]:
                data["overrides"]["file_length_limit"] = limit
                changes.append(f"Consolidated file length limit ({limit}) into overrides.file_length_limit")
                applied_steps.append("Consolidate file length limit in overrides")

        if "require_mutation_testing" in data:
            mut_val = bool(data["require_mutation_testing"])
            if "overrides" not in data or not isinstance(data["overrides"], dict):
                data["overrides"] = {}
            if "require_mutation_testing" not in data["overrides"]:
                data["overrides"]["require_mutation_testing"] = mut_val
                changes.append(f"Consolidated require_mutation_testing ({mut_val}) into overrides")
                applied_steps.append("Consolidate mutation testing requirement in overrides")

    def _split_content(
        self, content: str
    ) -> tuple[bool, str, str, list[str]]:
        lines = content.splitlines(keepends=True)
        header_comments: list[str] = []

        if content.startswith("---"):
            first_newline = content.find("\n")
            if first_newline != -1:
                m = re.search(r"(\r?\n)---[ \t]*(\r?\n|\Z)", content[first_newline:])
                if m:
                    closing_start = first_newline + m.start()
                    closing_end = first_newline + m.end()
                    raw_yaml = content[first_newline + 1 : closing_start]
                    body = content[closing_end:]
                    return True, raw_yaml, body, header_comments

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("#"):
                header_comments.append(line.rstrip("\r\n"))
            elif not stripped:
                header_comments.append("")
            else:
                break

        return False, content, "", header_comments

    def _render_content(
        self,
        data: dict[str, Any],
        has_frontmatter: bool,
        body: str,
        header_comments: list[str],
    ) -> str:
        dumped_yaml = yaml.dump(
            data,
            sort_keys=False,
            default_flow_style=False,
            allow_unicode=True,
        ).strip()

        if has_frontmatter:
            return f"---\n{dumped_yaml}\n---\n{body}"

        if header_comments:
            c_text = "\n".join(header_comments)
            return f"{c_text}\n{dumped_yaml}\n"

        return f"{dumped_yaml}\n"
