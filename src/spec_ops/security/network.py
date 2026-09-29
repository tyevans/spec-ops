"""Socket-level network egress restrictions and unprivileged network isolation."""

from __future__ import annotations

import contextlib
import ipaddress
import socket
from pathlib import Path
from typing import Any, Generator

LOOPBACK_HOSTNAMES = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}


def is_loopback_address(host: str) -> bool:
    """Evaluates whether an IP address or hostname represents a local loopback interface."""
    cleaned = host.strip().lower()
    if cleaned in LOOPBACK_HOSTNAMES:
        return True

    # Check for IP literal representation
    try:
        ip = ipaddress.ip_address(cleaned)
        return ip.is_loopback
    except ValueError:
        pass

    return False


@contextlib.contextmanager
def isolated_network() -> Generator[None, None, None]:
    """Context manager enforcing socket-level egress isolation for the current process.

    Blocks all outbound TCP and UDP socket connections to non-loopback addresses.
    """
    orig_connect = socket.socket.connect
    orig_sendto = socket.socket.sendto

    def sandboxed_connect(self: socket.socket, address: Any) -> None:
        if self.family in (socket.AF_INET, socket.AF_INET6):
            host = address[0] if isinstance(address, tuple) and address else address
            if not is_loopback_address(str(host)):
                raise PermissionError(
                    f"Architectural boundary violation: Outbound network egress to '{host}' blocked by sandbox."
                )
        return orig_connect(self, address)

    def sandboxed_sendto(self: socket.socket, data: bytes, *args: Any) -> int:
        if args and self.family in (socket.AF_INET, socket.AF_INET6):
            address = args[0]
            host = address[0] if isinstance(address, tuple) and address else address
            if not is_loopback_address(str(host)):
                raise PermissionError(
                    f"Architectural boundary violation: Outbound UDP egress to '{host}' blocked by sandbox."
                )
        return orig_sendto(self, data, *args)

    socket.socket.connect = sandboxed_connect  # type: ignore
    socket.socket.sendto = sandboxed_sendto  # type: ignore

    try:
        yield
    finally:
        socket.socket.connect = orig_connect  # type: ignore
        socket.socket.sendto = orig_sendto  # type: ignore


def generate_network_isolation_sitecustomize(output_dir: Path) -> Path:
    """Generates sitecustomize.py for subprocess network egress enforcement via PYTHONPATH."""
    output_dir.mkdir(parents=True, exist_ok=True)
    sitecustomize_path = output_dir / "sitecustomize.py"

    code = '''"""SpecOps Subprocess Network Egress Interceptor."""
import contextlib
import ipaddress
import socket
from typing import Any

LOOPBACK_HOSTNAMES = {"localhost", "127.0.0.1", "::1", "0.0.0.0"}

def _is_loopback(host: str) -> bool:
    cleaned = host.strip().lower()
    if cleaned in LOOPBACK_HOSTNAMES:
        return True
    try:
        return ipaddress.ip_address(cleaned).is_loopback
    except ValueError:
        return False

_orig_connect = socket.socket.connect
_orig_sendto = socket.socket.sendto

def _sandboxed_connect(self: socket.socket, address: Any) -> None:
    if self.family in (socket.AF_INET, socket.AF_INET6):
        host = address[0] if isinstance(address, tuple) and address else address
        if not _is_loopback(str(host)):
            raise PermissionError(
                f"Architectural boundary violation: Outbound network egress to '{host}' blocked by sandbox."
            )
    return _orig_connect(self, address)

def _sandboxed_sendto(self: socket.socket, data: bytes, *args: Any) -> int:
    if args and self.family in (socket.AF_INET, socket.AF_INET6):
        address = args[0]
        host = address[0] if isinstance(address, tuple) and address else address
        if not _is_loopback(str(host)):
            raise PermissionError(
                f"Architectural boundary violation: Outbound UDP egress to '{host}' blocked by sandbox."
            )
    return _orig_sendto(self, data, *args)

socket.socket.connect = _sandboxed_connect
socket.socket.sendto = _sandboxed_sendto
'''
    sitecustomize_path.write_text(code, encoding="utf-8")
    return sitecustomize_path
