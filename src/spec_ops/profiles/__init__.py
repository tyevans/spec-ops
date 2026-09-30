"""Architectural profiles and baseline ADRs for SpecOps."""

from .composer import (
    ResolvedComposition,
    compose_profiles,
    load_profile_definition,
    merge_overrides,
    parse_adr_content,
    parse_profile_toml,
    resolve_inheritance_dag,
)
from .models import (
    ADRCollisionError,
    BaselineADR,
    Profile,
    ProfileError,
    ProfileInheritanceError,
)
from .diff import (
    ADRDiff,
    ConfigDiff,
    InvariantDiff,
    ProfileSemanticDiff,
    compute_profile_diff,
)
from .migration import (
    ADRConflict,
    MigrationResult,
    detect_adr_conflicts,
    execute_profile_migration,
)
from .packager import (
    install_profile_bundle,
    load_profile_from_bundle,
    package_profile,
    validate_profile_source,
)
from .registry import (
    PROFILE_RELEASES,
    PROFILES,
    get_profile,
    list_profiles,
    register_profile_release,
    resolve_adrs_for_profiles,
)

__all__ = [
    "ADRCollisionError",
    "ADRConflict",
    "ADRDiff",
    "BaselineADR",
    "ConfigDiff",
    "InvariantDiff",
    "MigrationResult",
    "PROFILE_RELEASES",
    "PROFILES",
    "Profile",
    "ProfileError",
    "ProfileInheritanceError",
    "ProfileSemanticDiff",
    "ResolvedComposition",
    "compose_profiles",
    "compute_profile_diff",
    "detect_adr_conflicts",
    "execute_profile_migration",
    "get_profile",
    "install_profile_bundle",
    "list_profiles",
    "load_profile_definition",
    "load_profile_from_bundle",
    "merge_overrides",
    "package_profile",
    "parse_adr_content",
    "parse_profile_toml",
    "register_profile_release",
    "resolve_adrs_for_profiles",
    "resolve_inheritance_dag",
    "validate_profile_source",
]

