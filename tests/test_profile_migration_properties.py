"""Hypothesis generative property tests for profile migration engine (ADR-0009).

Asserts that migrating any valid legacy profile configuration produces a schema-valid
target profile without data loss or key corruption, and preserves idempotency.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st
import pytest
import yaml

from spec_ops.core.profile_migration import ProfileMigrator

st_profile_name = st.sampled_from(["core", "security", "enterprise", "bdd", "ddd", "custom-arch"])
st_version_str = st.sampled_from(["1.0.0", "1.0", "v1.0", "1", "0.9.0", None])
st_rule_name = st.from_regex(r"^[a-z][a-z0-9_-]{2,20}$", fullmatch=True)
st_rules_list = st.lists(st_rule_name, min_size=0, max_size=5, unique=True)

st_custom_scalar = st.one_of(
    st.integers(min_value=1, max_value=10000),
    st.booleans(),
    st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\n\r\x00"), min_size=1, max_size=30).map(lambda s: s.strip() or "val"),
)

st_custom_dict = st.dictionaries(
    keys=st.from_regex(r"^[a-z][a-z0-9_]{1,15}$", fullmatch=True),
    values=st_custom_scalar,
    min_size=0,
    max_size=4,
)

st_legacy_profile_data = st.fixed_dictionaries(
    {},
    optional={
        "profile": st.one_of(st_profile_name, st.lists(st_profile_name, min_size=1, max_size=3)),
        "version": st_version_str,
        "schema_version": st_version_str,
        "rules": st_rules_list,
        "custom_rules": st_rules_list,
        "rule_extensions": st_custom_dict,
        "file_length_limit": st.integers(min_value=100, max_value=1000),
        "require_mutation_testing": st.booleans(),
        "custom_overrides": st_custom_dict,
        "extra_custom_key": st_custom_scalar,
    },
).map(lambda d: {k: v for k, v in d.items() if v is not None})


@settings(max_examples=50, deadline=None)
@given(
    data=st_legacy_profile_data,
    use_frontmatter=st.booleans(),
    body_text=st.text(alphabet=st.characters(blacklist_categories=("Cs",), blacklist_characters="\r\x00"), max_size=100),
)
def test_property_migrating_legacy_profile_produces_valid_v2_schema(
    tmp_path_factory: pytest.TempPathFactory,
    data: dict[str, Any],
    use_frontmatter: bool,
    body_text: str,
) -> None:
    tmp_dir = tmp_path_factory.mktemp("mig_prop")
    profile_path = tmp_dir / "profile.yaml"

    original_input = copy.deepcopy(data)
    # Ensure at least a profile or name is present so it's a valid legacy input
    if not any(k in original_input for k in ("profile", "profiles", "name", "id", "rules", "overrides")):
        original_input["profile"] = "core"

    clean_yaml = yaml.dump(original_input, sort_keys=False, default_flow_style=False).strip()
    if use_frontmatter:
        clean_body = body_text.strip() or "Standard markdown documentation"
        file_content = f"---\n{clean_yaml}\n---\n# Architecture Profile\n{clean_body}\n"
    else:
        file_content = f"# Configuration Header\n{clean_yaml}\n"

    profile_path.write_text(file_content, encoding="utf-8")

    migrator = ProfileMigrator()
    success, report = migrator.migrate(profile_path, target_version="2.0.0")

    # 1. Migration must succeed
    assert success is True
    assert report.to_version == "2.0.0"

    # 2. Migrated file must conform to schema 2.0.0
    migrated_text = profile_path.read_text(encoding="utf-8")
    _, raw_m_yaml, m_body, _ = migrator._split_content(migrated_text)
    migrated_dict = yaml.safe_load(raw_m_yaml)

    assert isinstance(migrated_dict, dict)
    validation_errors = migrator.validate_schema(migrated_dict, version="2.0.0")
    assert validation_errors == [], f"Validation errors on migrated schema: {validation_errors}"

    # 3. No data loss: all custom keys, rules, and overrides must be preserved
    if "custom_rules" in original_input:
        assert migrated_dict.get("custom_rules") == original_input["custom_rules"]
    if "rule_extensions" in original_input:
        assert migrated_dict.get("rule_extensions") == original_input["rule_extensions"]
    if "custom_overrides" in original_input:
        assert migrated_dict.get("custom_overrides") == original_input["custom_overrides"]
    if "extra_custom_key" in original_input:
        assert migrated_dict.get("extra_custom_key") == original_input["extra_custom_key"]

    # 4. If legacy limits existed, they are preserved in overrides
    if "file_length_limit" in original_input:
        assert migrated_dict.get("overrides", {}).get("file_length_limit") == original_input["file_length_limit"]
    if "require_mutation_testing" in original_input:
        assert migrated_dict.get("overrides", {}).get("require_mutation_testing") == original_input["require_mutation_testing"]

    # 5. If frontmatter body was present, body content must be preserved
    if use_frontmatter:
        clean_body = body_text.strip() or "Standard markdown documentation"
        assert clean_body in m_body

    # 6. Idempotency: re-running migration on the upgraded profile confirms up to date
    success_2, report_2 = migrator.migrate(profile_path, target_version="2.0.0")
    assert success_2 is True
    assert report_2.is_up_to_date is True
    assert report_2.changes == []
