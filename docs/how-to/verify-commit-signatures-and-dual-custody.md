# How-To: Verify Commit Signatures and Enforce Dual-Custody Review

This guide covers configuring cryptographic commit signature verification (GPG/SSH) and conducting mandatory human dual-custody review sign-offs before autonomous tasks can be completed and merged.

---

## Configuring Compliance Settings

To mandate cryptographic commit signatures and dual custody, configure `[security.compliance]` in `spec-ops.toml`:

```toml
[security.compliance]
require_signed_commits = true
dual_custody = true
allowed_signers_file = ".ssh/allowed_signers"
authorized_signers = [
    "Riley Reviewer <riley@example.com>",
    "Jordan Architect <jordan@example.com>",
]
```

When `require_signed_commits = true`:
1. Every git commit on feature branches must be signed with a valid GPG or SSH key (`%G?` in `G` or `U`).
2. Any unsigned commit causes `spec-ops queue complete <task-id>` or worker merge to abort with returncode 1:
   ```text
   Compliance Violation: Commit <sha> lacks valid cryptographic signature (GPG/SSH)
   ```

---

## Signing Off on Autonomous Agent Tasks

When dual custody is enabled, autonomous agent tasks require an authorized human review before completion.

To verify reviewer identity and record sign-off:

```bash
spec-ops review sign TASK-0030 --identity "Riley Reviewer <riley@example.com>"
```

The command:
1. Validates the identity format (RFC 2822 or GPG/SSH key ID).
2. Verifies the identity against authorized signers in `spec-ops.toml` or the SSH `allowed_signers` keyring.
3. Updates task frontmatter with `signed_off_by` and UTC ISO-8601 timestamp:
   ```yaml
   signed_off_by: Riley Reviewer <riley@example.com>
   signed_off_at: '2026-09-29T17:00:00+00:00'
   ```

---

## Gating Backlog Integration Under Dual Control

Once signed off, complete the task:

```bash
spec-ops queue complete TASK-0030
```

When integrating to the base branch:
- Verified commit signatures are validated.
- Dual-custody review metadata is checked.
- Structured git trailers `SpecOps-Task: TASK-0030` and `SpecOps-Signed-By: <identity>` are injected into the squash commit.
