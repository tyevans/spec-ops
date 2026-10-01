"""Extensible Shannon entropy secret scanner rule plugin engine.

Computes Shannon entropy H(X) = -sum(p * log2(p)) for characters in candidate tokens,
enforcing project-configurable secret detection rules, dynamic allowlists, and pragma defenses.
"""

from __future__ import annotations

import collections
import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

__all__ = [
    "DEFAULT_BASE64_THRESHOLD",
    "DEFAULT_MIN_LENGTH",
    "EntropyFinding",
    "EntropyRule",
    "EntropyScannerConfig",
    "PRAGMA_ALLOWLIST_PATTERN",
    "SHA_PATTERN",
    "ShannonEntropyScanner",
    "UUID_PATTERN",
    "calculate_entropy",
]

DEFAULT_MIN_LENGTH = 20
DEFAULT_BASE64_THRESHOLD = 4.5

UUID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)
SHA_PATTERN = re.compile(r"^(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})$")
PRAGMA_ALLOWLIST_PATTERN = re.compile(
    r"(?:#|//|/\*)\s*(?:pragma:\s*allowlist[-_\s]secret|spec-ops:\s*ignore[-_]secret)",
    re.IGNORECASE,
)
EXCLUDED_SCAN_DIRS = frozenset({
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".hypothesis",
    "__pycache__",
    "node_modules",
    ".idea",
    ".vscode",
    ".worktrees",
    "dist",
    "build",
    "eggs",
    ".eggs",
})

EXCLUDED_SCAN_FILES = frozenset({
    "uv.lock",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "poetry.lock",
    "Pipfile.lock",
    "Cargo.lock",
    "go.sum",
    "composer.lock",
})

EXCLUDED_SCAN_EXTENSIONS = frozenset({
    ".lock",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".ico",
    ".svg",
    ".pyc",
    ".tar",
    ".gz",
    ".zip",
    ".whl",
})


def calculate_entropy(text: str) -> float:
    """Computes Shannon entropy in bits for characters in candidate tokens.

    Formula: H(X) = -sum(p(x) * log2(p(x)))
    Returns a value bounded strictly in [0.0, 8.0] and <= log2(len(set(text))).
    """
    if not text:
        return 0.0

    total_len = len(text)
    counts = collections.Counter(text)
    num_unique = len(counts)
    if num_unique <= 1:
        return 0.0

    entropy = 0.0
    for count in counts.values():
        p = count / total_len
        # pragma: no mutate start
        if p > 0.0:
            entropy -= p * math.log2(p)
        # pragma: no mutate end

    max_theoretical = math.log2(num_unique)
    if entropy > max_theoretical:
        entropy = max_theoretical
    if entropy < 0.0:
        entropy = 0.0
    if entropy > 8.0:
        entropy = 8.0

    return float(entropy)


@dataclass
class EntropyRule:
    name: str
    threshold: float = DEFAULT_BASE64_THRESHOLD
    min_length: int = DEFAULT_MIN_LENGTH
    alphabet_type: str = "all"
    custom_regex: str = ""

    def __post_init__(self) -> None:
        valid_alphabets = {"base64", "hex", "alphanumeric", "all"}
        if self.alphabet_type not in valid_alphabets:
            raise ValueError(
                f"Invalid alphabet_type '{self.alphabet_type}'. Must be one of {sorted(valid_alphabets)}"
            )


@dataclass
class EntropyFinding:
    token: str
    line_number: int
    file_path: str
    entropy: float
    rule_name: str
    reason: str

    @property
    def masked_token(self) -> str:
        if len(self.token) <= 8:
            return "****"
        return f"{self.token[:4]}****{self.token[-4:]}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "masked_token": self.masked_token,
            "line_number": self.line_number,
            "file_path": self.file_path,
            "entropy": round(self.entropy, 4),
            "rule_name": self.rule_name,
            "reason": self.reason,
        }


@dataclass
class EntropyScannerConfig:
    rules: list[EntropyRule] = field(default_factory=list)
    allowlist_patterns: list[str] = field(default_factory=list)
    ignore_uuids: bool = True
    ignore_shas: bool = True

    def __post_init__(self) -> None:
        if not self.rules:
            self.rules = [
                EntropyRule(
                    name="default-entropy",
                    threshold=DEFAULT_BASE64_THRESHOLD,
                    min_length=DEFAULT_MIN_LENGTH,
                    alphabet_type="all",
                )
            ]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EntropyScannerConfig:
        cfg_data = data.get("entropy", data) if isinstance(data, dict) else {}
        if not isinstance(cfg_data, dict):
            cfg_data = {}

        rules: list[EntropyRule] = []
        for r in cfg_data.get("rules", []):
            if isinstance(r, dict):
                rules.append(
                    EntropyRule(
                        name=str(r.get("name", "custom-rule")),
                        threshold=float(r.get("threshold", DEFAULT_BASE64_THRESHOLD)),
                        min_length=int(r.get("min_length", DEFAULT_MIN_LENGTH)),
                        alphabet_type=str(r.get("alphabet_type", "all")),
                        custom_regex=str(r.get("custom_regex", "")),
                    )
                )

        raw_patterns = cfg_data.get("allowlist_patterns", [])
        patterns = [str(p) for p in raw_patterns] if isinstance(raw_patterns, list) else []
        return cls(
            rules=rules,
            allowlist_patterns=patterns,
            ignore_uuids=bool(cfg_data.get("ignore_uuids", True)),
            ignore_shas=bool(cfg_data.get("ignore_shas", True)),
        )

    @classmethod
    def from_yaml(cls, yaml_content: str) -> EntropyScannerConfig:
        data = yaml.safe_load(yaml_content) or {}
        return cls.from_dict(data)

    @classmethod
    def load_from_project(cls, root_dir: Path | None = None) -> EntropyScannerConfig:
        root = (root_dir or Path.cwd()).resolve()
        for filename in (".specops/security.yaml", ".specops/security.yml"):
            target = root / filename
            if target.is_file():
                try:
                    return cls.from_yaml(target.read_text(encoding="utf-8"))
                except Exception:
                    pass
        return cls()


class ShannonEntropyScanner:
    """Evaluates source code and text tokens for high-entropy secrets and credential risks."""

    def __init__(self, config: EntropyScannerConfig | None = None) -> None:
        self.config = config if config is not None else EntropyScannerConfig()

    @staticmethod
    def calculate_entropy(text: str) -> float:
        return calculate_entropy(text)

    def is_ignored(self, token: str) -> bool:
        if self.config.ignore_uuids and UUID_PATTERN.match(token):
            return True
        if self.config.ignore_shas and SHA_PATTERN.match(token):
            return True
        for pat in self.config.allowlist_patterns:
            try:
                if re.search(pat, token):
                    return True
            except re.error:
                if pat in token:
                    return True
        return False

    def extract_candidates(self, line: str, rule: EntropyRule) -> list[str]:
        candidates: list[str] = []
        if rule.custom_regex:
            try:
                rx = re.compile(rule.custom_regex)
                for m in rx.finditer(line):
                    cand = m.group(1) if m.groups() else m.group(0)
                    if len(cand) >= rule.min_length:
                        candidates.append(cand)
            except re.error:
                pass
            return candidates

        if rule.alphabet_type == "hex":
            for m in re.finditer(
                r"(?i)(?<![0-9a-fA-F])([0-9a-fA-F]{" + str(rule.min_length) + r",})(?![0-9a-fA-F])",
                line,
            ):
                candidates.append(m.group(1))
        elif rule.alphabet_type == "alphanumeric":
            for m in re.finditer(
                r"(?<![0-9a-zA-Z])([0-9a-zA-Z]{" + str(rule.min_length) + r",})(?![0-9a-zA-Z])",
                line,
            ):
                candidates.append(m.group(1))
        elif rule.alphabet_type == "base64":
            for m in re.finditer(
                r"(?<![A-Za-z0-9+/=_-])([A-Za-z0-9+/=_-]{" + str(rule.min_length) + r",})(?![A-Za-z0-9+/=_-])",
                line,
            ):
                candidates.append(m.group(1))
        else:  # "all"
            for m in re.finditer(r"['\"]([^'\"]{" + str(rule.min_length) + r",})['\"]", line):
                candidates.append(m.group(1))
            unquoted = re.sub(r"['\"][^'\"]*['\"]", " ", line)
            for word in unquoted.split():
                if "=" in word and not word.endswith("="):
                    word = word.split("=", 1)[-1]
                clean = word.strip("'\"` ;,()[]{}")
                if len(clean) >= rule.min_length and clean not in candidates:
                    candidates.append(clean)
        return candidates

    def scan_text(self, text: str, file_path: str = "") -> list[EntropyFinding]:
        findings: list[EntropyFinding] = []
        lines = text.splitlines()
        seen_line_tokens: set[tuple[int, str]] = set()

        for idx, line in enumerate(lines, start=1):
            if PRAGMA_ALLOWLIST_PATTERN.search(line):
                continue
            if idx > 1 and PRAGMA_ALLOWLIST_PATTERN.search(lines[idx - 2]):
                continue

            for rule in self.config.rules:
                candidates = self.extract_candidates(line, rule)
                for cand in candidates:
                    if (idx, cand) in seen_line_tokens:
                        continue
                    if self.is_ignored(cand):
                        continue
                    entropy = calculate_entropy(cand)
                    if entropy >= rule.threshold:
                        seen_line_tokens.add((idx, cand))
                        reason = (
                            f"Shannon entropy ({entropy:.2f}) exceeds rule '{rule.name}' "
                            f"threshold ({rule.threshold:.2f})"
                        )
                        findings.append(
                            EntropyFinding(
                                token=cand,
                                line_number=idx,
                                file_path=file_path,
                                entropy=entropy,
                                rule_name=rule.name,
                                reason=reason,
                            )
                        )
        return findings

    def scan_file(self, path: Path) -> list[EntropyFinding]:
        if not path.is_file():
            return []
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return []
        return self.scan_text(content, file_path=str(path))

    def scan_directory(self, directory: Path) -> list[EntropyFinding]:
        findings: list[EntropyFinding] = []
        if not directory.is_dir():
            return findings
        for item in sorted(directory.rglob("*")):
            if not item.is_file():
                continue
            if any(part in EXCLUDED_SCAN_DIRS for part in item.parts):
                continue
            if item.name in EXCLUDED_SCAN_FILES or item.suffix in EXCLUDED_SCAN_EXTENSIONS:
                continue
            findings.extend(self.scan_file(item))
        return findings
