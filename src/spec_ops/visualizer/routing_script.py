"""Client-side URL hash routing and bidirectional state synchronization.

Re-exports from url_router_script to preserve backward compatibility.
"""
from __future__ import annotations

from .url_router_script import (
    ROUTING_JS,
    URL_ROUTER_JS,
    VisualizerUrlState,
    parse_url_hash,
    serialize_url_hash,
)

__all__ = [
    "ROUTING_JS",
    "URL_ROUTER_JS",
    "VisualizerUrlState",
    "parse_url_hash",
    "serialize_url_hash",
]
