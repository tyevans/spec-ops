"""Pure Python zero-dependency RFC 8032 Edwards25519 digital signature engine."""

from __future__ import annotations

import base64
import hashlib

# Edwards25519 Field and Group Constants (RFC 8032)
_P = 2**255 - 19
_Q = 2**252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _inv(z: int) -> int:
    return pow(z, _P - 2, _P)


def _point_add(P: tuple[int, int], Q: tuple[int, int]) -> tuple[int, int]:
    x1, y1 = P
    x2, y2 = Q
    x3 = (x1 * y2 + x2 * y1) * _inv(1 + _D * x1 * x2 * y1 * y2) % _P
    y3 = (y1 * y2 + x1 * x2) * _inv(1 - _D * x1 * x2 * y1 * y2) % _P
    return (x3, y3)


def _point_mul(s: int, P: tuple[int, int]) -> tuple[int, int]:
    Q = (0, 1)
    while s > 0:
        if s & 1:
            Q = _point_add(Q, P)
        P = _point_add(P, P)
        s >>= 1
    return Q


def _recover_x(y: int, sign: int) -> int | None:
    if y >= _P:
        return None
    x2 = (y * y - 1) * _inv(_D * y * y + 1) % _P
    if x2 == 0:
        return 0 if sign == 0 else None
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P != 0:
        x = (x * _I) % _P
    if (x * x - x2) % _P != 0:
        return None
    if (x & 1) != sign:
        x = _P - x
    return x


_BY = 4 * _inv(5) % _P
_BX = _recover_x(_BY, 0)
assert _BX is not None
_B: tuple[int, int] = (_BX, _BY)


def _point_to_bytes(P: tuple[int, int]) -> bytes:
    x, y = P
    b = bytearray(y.to_bytes(32, "little"))
    if x & 1:
        b[31] |= 0x80
    return bytes(b)


def _bytes_to_point(b: bytes) -> tuple[int, int] | None:
    if len(b) != 32:
        return None
    y = int.from_bytes(bytes([b[i] if i < 31 else b[i] & 0x7F for i in range(32)]), "little")
    sign = (b[31] >> 7) & 1
    x = _recover_x(y, sign)
    return (x, y) if x is not None else None


def ed25519_keypair(seed: bytes) -> tuple[bytes, bytes]:
    """Generates an Ed25519 private seed and 32-byte public key."""
    if len(seed) != 32:
        seed = hashlib.sha256(seed).digest()
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 1
    a &= ~7
    a |= 1 << 254
    A = _point_mul(a, _B)
    return seed, _point_to_bytes(A)


def ed25519_sign(seed: bytes, public_key: bytes, msg: bytes) -> bytes:
    """Signs message with Ed25519 private seed, returning a 64-byte signature."""
    if len(seed) != 32:
        seed = hashlib.sha256(seed).digest()
    h = hashlib.sha512(seed).digest()
    a = int.from_bytes(h[:32], "little")
    a &= (1 << 254) - 1
    a &= ~7
    a |= 1 << 254
    r = int.from_bytes(hashlib.sha512(h[32:] + msg).digest(), "little") % _Q
    R = _point_mul(r, _B)
    R_bytes = _point_to_bytes(R)
    k = int.from_bytes(hashlib.sha512(R_bytes + public_key + msg).digest(), "little") % _Q
    S = (r + k * a) % _Q
    return R_bytes + S.to_bytes(32, "little")


def ed25519_verify(public_key: bytes, msg: bytes, sig: bytes) -> bool:
    """Verifies an Ed25519 signature against message and 32-byte public key."""
    if len(sig) != 64 or len(public_key) != 32:
        return False
    R_bytes, S_bytes = sig[:32], sig[32:]
    S = int.from_bytes(S_bytes, "little")
    if S >= _Q:
        return False
    A = _bytes_to_point(public_key)
    R = _bytes_to_point(R_bytes)
    if A is None or R is None:
        return False
    k = int.from_bytes(hashlib.sha512(R_bytes + public_key + msg).digest(), "little") % _Q
    return _point_mul(S, _B) == _point_add(R, _point_mul(k, A))


def ssh_encode_ed25519_pub(pub_bytes: bytes) -> str:
    """Formats 32-byte Ed25519 public key as OpenSSH public key string."""
    type_b = b"ssh-ed25519"
    wire = len(type_b).to_bytes(4, "big") + type_b + len(pub_bytes).to_bytes(4, "big") + pub_bytes
    return f"ssh-ed25519 {base64.b64encode(wire).decode('ascii')}"


def ssh_decode_ed25519_pub(raw: str) -> bytes | None:
    """Extracts raw 32-byte Ed25519 public key from SSH or base64/hex string."""
    clean = raw.strip()
    if not clean:
        return None
    if len(clean) == 64:
        try:
            return bytes.fromhex(clean)
        except ValueError:
            pass
    parts = clean.split()
    if not parts:
        return None
    b64_str = parts[1] if len(parts) >= 2 and parts[0] == "ssh-ed25519" else parts[0]
    try:

        decoded = base64.b64decode(b64_str)
    except Exception:
        return None
    if len(decoded) == 32:
        return decoded
    if len(decoded) >= 51:
        idx = 0
        l1 = int.from_bytes(decoded[idx : idx + 4], "big")
        idx += 4 + l1
        l2 = int.from_bytes(decoded[idx : idx + 4], "big")
        idx += 4
        return decoded[idx : idx + l2]
    return None
