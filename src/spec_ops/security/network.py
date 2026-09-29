"""Backward-compatibility re-exports for network guard module."""

from __future__ import annotations

from .network_guard import (
    LOOPBACK_HOSTNAMES,
    generate_network_isolation_sitecustomize,
    is_loopback_address,
    isolated_network,
)

__all__ = [
    "LOOPBACK_HOSTNAMES",
    "generate_network_isolation_sitecustomize",
    "is_loopback_address",
    "isolated_network",
]
