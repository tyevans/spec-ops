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
from .packager import (
    install_profile_bundle,
    load_profile_from_bundle,
    package_profile,
    validate_profile_source,
)
from .registry import (
    PROFILES,
    get_profile,
    list_profiles,
    resolve_adrs_for_profiles,
)

__all__ = [
    "ADRCollisionError",
    "BaselineADR",
    "PROFILES",
    "Profile",
    "ProfileError",
    "ProfileInheritanceError",
    "ResolvedComposition",
    "compose_profiles",
    "get_profile",
    "install_profile_bundle",
    "list_profiles",
    "load_profile_definition",
    "load_profile_from_bundle",
    "merge_overrides",
    "package_profile",
    "parse_adr_content",
    "parse_profile_toml",
    "resolve_adrs_for_profiles",
    "resolve_inheritance_dag",
    "validate_profile_source",
]
