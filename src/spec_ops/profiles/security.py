"""Enterprise Security & Supply-Chain Profile definition and guardrails."""

from __future__ import annotations

import re
from pathlib import Path

from .models import BaselineADR, Profile

# pragma: no mutate start
SECURITY_ADR_0010 = BaselineADR(
    number=10,
    slug="zero-trust-worker-process-sandboxing",
    title="Zero-Trust Autonomous Worker Process Sandboxing",
    content="""# ADR-0010: Zero-Trust Autonomous Worker Process Sandboxing

## Status
Accepted

## Context
Autonomous coding agents running unrestricted shell commands in developer environments pose significant supply-chain, privilege escalation, and lateral movement risks.

## Decision
We enforce **Zero-Trust Autonomous Worker Process Sandboxing**:
1. Autonomous worker processes execute in isolated sandboxes with strict command allowlisting.
2. Arbitrary shell command execution outside approved development toolchains is blocked.
3. Network egress during autonomous code generation is monitored and restricted.

## Consequences
- **Positive**: Prevents unauthorized execution, supply-chain exfiltration, and destructive commands.
- **Negative**: Requires explicit allowlisting of development tools and commands.
""",
)

SECURITY_ADR_0011 = BaselineADR(
    number=11,
    slug="immutable-supply-chain-lockfile-enforcement",
    title="Immutable Supply-Chain Lockfile Enforcement",
    content="""# ADR-0011: Immutable Supply-Chain Lockfile Enforcement

## Status
Accepted

## Context
LLMs frequently hallucinate dependency names or introduce malicious or vulnerable packages into lockfiles without verification.

## Decision
We enforce **Immutable Supply-Chain Lockfile Enforcement**:
1. Autonomous agents are strictly forbidden from modifying lockfiles (`uv.lock`, `package-lock.json`) without explicit human approval.
2. Preflight verification enforces strict lockfile integrity checks (`uv lock --check`).
3. Dependency updates must undergo human-reviewed security audits.

## Consequences
- **Positive**: Eliminates hallucinated package attacks, dependency confusion, and untracked supply-chain drifts.
- **Negative**: Adding new dependencies requires an explicit human review step.
""",
)

SECURITY_ADR_0012 = BaselineADR(
    number=12,
    slug="secret-scanning-and-credential-leak-defense",
    title="Real-Time Secret Scanning and Credential Leak Defense",
    content="""# ADR-0012: Real-Time Secret Scanning and Credential Leak Defense

## Status
Accepted

## Context
Hardcoded credentials, API tokens, and private keys committed to git repositories cause catastrophic data leaks that persist forever in commit histories.

## Decision
We enforce **Real-Time Secret Scanning and Credential Leak Defense**:
1. Autonomous agents and human contributors are strictly forbidden from hardcoding credentials, tokens, or private keys.
2. Preflight and pre-commit hooks inspect diffs for high-entropy strings and known secret patterns.
3. Commits containing detected secrets are rejected immediately before staging or pushing.

## Consequences
- **Positive**: Guarantees zero credentials leak into git history or pull requests.
- **Negative**: Occasional false positives on high-entropy non-secret test fixtures require explicit inline ignores.
""",
)

SECURITY_PROFILE = Profile(
    id="security",
    name="Enterprise Security & Supply-Chain Guardrails",
    description="Zero-trust agent sandboxing, lockfile immutability, and automated secret scanning.",
    adrs=[SECURITY_ADR_0010, SECURITY_ADR_0011, SECURITY_ADR_0012],
)

DEFAULT_SECURITY_MD = """# Security Policy and Vulnerability Disclosure

## 1. Vulnerability Disclosure Policy & Workflows

We take the security of this system seriously. If you identify a security vulnerability, we request that you disclose it responsibly:
- **Private Reporting**: Do not disclose vulnerabilities in public issue trackers, pull requests, or discussion forums.
- **Response Timeline**: The security team acknowledges vulnerability reports within 24 hours and provides triage within 72 hours.
- **Coordinated Disclosure**: Fixes are developed in private security worktrees and published alongside advisories upon release.

## 2. Reporting Contacts & Incident Management

To report a vulnerability or security incident, contact the security team:
- **Primary Security Contact**: security@example.com
- **Incident Escalation**: security-incidents@example.com

## 3. PGP Key Fingerprint

Submissions containing sensitive vulnerability descriptions should be encrypted using our PGP key:
- **PGP Fingerprint**: `ABCD 1234 EF56 7890 ABCD 1234 EF56 7890 SPEC OPS1`
- **Key Server**: `keys.openpgp.org`

## 4. Autonomous Worker Execution Restrictions

Autonomous coding agents executing in this repository must operate under zero-trust constraints:
1. Forbids agents from hardcoding credentials, API keys, or secrets.
2. Forbids agents from modifying unapproved lockfiles.
3. Forbids agents from executing non-allowlisted shell commands.
"""

DEFAULT_SECURITY_TOML = """[security]
secret_scanning = true
lockfile_immutability = true
enforce_lockfile = true
sandbox_enabled = true
allowed_commands = ["pytest", "git", "uv"]
reporting_contact = "security@example.com"
"""
# pragma: no mutate end

SECURITY_RESTORATION_GUIDANCE = (
    "Security Policy Invariant Violated: docs/project/SECURITY.md is missing or invalid. "
    "Run 'spec-ops profile sync security' to restore"
)

CONFIG_RESTORATION_GUIDANCE = (
    "Security Policy Invariant Violated: specops.toml missing [security] configuration. "
    "Run 'spec-ops profile sync security' to restore"
)

REQUIRED_POLICY_MARKERS = (
    "Vulnerability Disclosure",
    "Reporting Contacts",
    "PGP Fingerprint",
)


def validate_security_policy(root_dir: Path) -> tuple[bool, str]:
    """Validates existence and specification compliance of docs/project/SECURITY.md and specops.toml."""
    sec_md = root_dir / "docs" / "project" / "SECURITY.md"
    if not sec_md.is_file():
        return False, SECURITY_RESTORATION_GUIDANCE

    try:
        content = sec_md.read_text(encoding="utf-8")  # pragma: no mutate
    except OSError:
        return False, SECURITY_RESTORATION_GUIDANCE

    if len(content) < 50:
        return False, SECURITY_RESTORATION_GUIDANCE

    for marker in REQUIRED_POLICY_MARKERS:
        if marker not in content:
            return False, SECURITY_RESTORATION_GUIDANCE

    toml_path = root_dir / "specops.toml"
    if toml_path.is_file():
        toml_content = toml_path.read_text(encoding="utf-8")  # pragma: no mutate
        if "[security]" not in toml_content:
            return False, CONFIG_RESTORATION_GUIDANCE

    return True, "Security policies and guardrails verified."


def scaffold_security_policy(root_dir: Path, overwrite: bool = False) -> Path:
    """Scaffolds docs/project/SECURITY.md in target repository."""
    sec_md = root_dir / "docs" / "project" / "SECURITY.md"
    sec_md.parent.mkdir(parents=True, exist_ok=True)
    if overwrite or not sec_md.exists():
        sec_md.write_text(DEFAULT_SECURITY_MD.strip() + "\n", encoding="utf-8")  # pragma: no mutate
    return sec_md


def install_security_adrs(root_dir: Path) -> list[Path]:
    """Installs baseline security ADRs and updates the ADR registry."""
    adrs_dir = root_dir / "docs" / "project" / "adrs" / "accepted"
    adrs_dir.mkdir(parents=True, exist_ok=True)

    installed: list[Path] = []
    registry_file = root_dir / "docs" / "project" / "adrs" / "REGISTRY.md"

    # Determine highest existing ADR number
    highest_num = 0
    for p in adrs_dir.glob("*.md"):
        m = re.match(r"^adr-(\d+)", p.name)
        if m:
            highest_num = max(highest_num, int(m.group(1)))

    existing_slugs = {p.stem for p in adrs_dir.glob("*.md")}

    for adr in SECURITY_PROFILE.adrs:
        if any(adr.slug in s for s in existing_slugs):
            continue
        highest_num += 1
        new_filename = f"adr-{highest_num:04d}-{adr.slug}.md"
        old_id = f"ADR-{adr.number:04d}"
        new_id = f"ADR-{highest_num:04d}"
        new_content = adr.content.replace(old_id, new_id)
        adr_path = adrs_dir / new_filename
        adr_path.write_text(new_content.strip() + "\n", encoding="utf-8")  # pragma: no mutate
        installed.append(adr_path)

        # Update REGISTRY.md if present
        if registry_file.exists():
            reg_text = registry_file.read_text(encoding="utf-8")  # pragma: no mutate
            if new_id not in reg_text:
                new_row = f"| {new_id} | {adr.title} | {adr.status} | {adr.date} |\n"
                registry_file.write_text(reg_text.rstrip() + "\n" + new_row, encoding="utf-8")  # pragma: no mutate

    return installed


def apply_security_profile(root_dir: Path) -> None:
    """Applies the security profile to an existing or new repository."""
    scaffold_security_policy(root_dir, overwrite=False)

    toml_path = root_dir / "specops.toml"
    if toml_path.exists():
        toml_content = toml_path.read_text(encoding="utf-8")  # pragma: no mutate
        if "[security]" not in toml_content:
            toml_path.write_text(toml_content.rstrip() + "\n\n" + DEFAULT_SECURITY_TOML.strip() + "\n", encoding="utf-8")  # pragma: no mutate
    else:
        toml_path.write_text(DEFAULT_SECURITY_TOML.strip() + "\n", encoding="utf-8")  # pragma: no mutate

    install_security_adrs(root_dir)

    from ..scaffold.agents_md import scaffold_agents_command
    scaffold_agents_command(root_dir)


def sync_security_profile(root_dir: Path) -> None:
    """Restores missing or degraded security artifacts."""
    scaffold_security_policy(root_dir, overwrite=True)

    toml_path = root_dir / "specops.toml"
    if toml_path.exists():
        toml_content = toml_path.read_text(encoding="utf-8")  # pragma: no mutate
        if "[security]" not in toml_content:
            toml_path.write_text(toml_content.rstrip() + "\n\n" + DEFAULT_SECURITY_TOML.strip() + "\n", encoding="utf-8")  # pragma: no mutate

    install_security_adrs(root_dir)

    from ..scaffold.agents_md import scaffold_agents_command
    scaffold_agents_command(root_dir)
